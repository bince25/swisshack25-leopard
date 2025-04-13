import eventlet
eventlet.monkey_patch()
# --- Add necessary imports ---
import json
import requests
import os
import threading
import uuid # For generating unique run IDs
import traceback # For detailed error logging
import re # Import regex for sanitization
import random # <<< Import random for generating rates >>>
from dotenv import load_dotenv # To load environment variables from .env file
from flask import Flask, request, jsonify # Import Flask
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room, leave_room # Import Flask-SocketIO
from typing import Any, Dict, List, Union, Optional, TYPE_CHECKING

# --- CrewAI Imports ---
from crewai import Agent, Task, Crew, Process
from langchain_openai import ChatOpenAI

# --- LangChain Callback Imports ---
from langchain.callbacks.base import BaseCallbackHandler
from langchain_core.outputs import LLMResult # To access token usage

# Import Task for type hinting in callbacks
from crewai import Task as CrewTask

if TYPE_CHECKING:
    from langchain_core.outputs import AgentAction, AgentFinish


# --- Load Environment Variables ---
load_dotenv()

# --- Configuration ---
HIERARCHY_API_ENDPOINT = "https://api.openai.com/v1/chat/completions"
HIERARCHY_API_KEY = os.getenv("OPENAI_API_KEY")

# --- Flask App and SocketIO Setup ---
app = Flask(__name__)
CORS(app)
# Secret key is needed for session management used by SocketIO
app.config['SECRET_KEY'] = os.getenv('FLASK_SECRET_KEY', 'a_default_secret_key_for_dev_123!')
# Allow all origins for development; restrict in production!
socketio = SocketIO(app, cors_allowed_origins="*")

# --- In-memory storage (Consider replacing with DB) ---
crew_results_storage = {}
storage_lock = threading.Lock() # Keep using lock for this shared storage

# --- LLM Configuration for CrewAI ---
# Check for API key existence
if not os.getenv("OPENAI_API_KEY"):
    print("*"*30)
    print("Warning: OPENAI_API_KEY environment variable not set.")
    print("*"*30)
    # Consider exiting if key is missing for core functionality
    # exit(1)

# Note: default_llm will be instantiated *inside* the background task
#       with the callback handler attached.

# --- Helper Function for API Key Check (Unchanged) ---
def check_api_key(key, key_name="API Key"):
    """Checks if the API key is present and not a placeholder."""
    if not key:
        print(f"Warning: {key_name} is not set in environment variables.")
        return False, f"{key_name} is not configured."
    # Add more sophisticated checks if needed (e.g., placeholder values)
    return True, None

# --- Hierarchy Generation Function (Unchanged) ---
def create_agent_hierarchy_with_ai(task_description: str) -> str:
    """Generates agent hierarchy JSON using an AI model."""
    key_ok, error_msg = check_api_key(HIERARCHY_API_KEY, "Hierarchy Generation API Key (OPENAI_API_KEY)")
    if not key_ok:
         print(f"Warning: {error_msg}")
         # Return error as JSON string, consistent with other returns
         return json.dumps({"error": error_msg})

    prompt = f"""
    Generate a hierarchical multi-agent system consisting 2 to 4 agents to plan to accomplish the following task: "{task_description}"

    The output should be a JSON array where each object represents an agent.
    Each agent object must have the following keys:
    - "agent_name": A descriptive name for the agent (string, use underscores for spaces).
    - "description": A brief explanation of the agent's role and responsibilities (string).
    - "level": An integer indicating the agent's level in the hierarchy (e.g., 1 for top-level, increasing for subsequent levels).
    - "cost_per_million": An integer indicating the agent's cost in million tokens.'
    - "tokens": Tokens that are needed to accomplish the task.

    Example for task "write a simple story":
    [
        {{"agent_name": "Plot_Generator", "description": "Creates the basic storyline...", "level": 1, "cost_per_million":1, "tokens": 1000}},
        {{"agent_name": "Chapter_Writer", "description": "Writes individual chapters...", "level": 2, "cost_per_million":10, "tokens": 3000}},
        {{"agent_name": "Dialogue_Specialist", "description": "Focuses on writing dialogue...", "level": 3, "cost_per_million":1, "tokens": 7000}},
        {{"agent_name": "Editor", "description": "Reviews the story...", "level": 4, "cost_per_million":2, "tokens": 3000}}
    ]

    Now, generate the JSON array for the task: "{task_description}"
    Provide *only* the JSON array as the output, without any introductory text or explanation. Ensure the output is valid JSON.
    """
    headers = {
        "Authorization": f"Bearer {HIERARCHY_API_KEY}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "gpt-3.5-turbo", # Model used for generating the hierarchy
        "messages": [
            {"role": "system", "content": "You are an expert in designing multi-agent systems and outputting valid JSON."},
            {"role": "user", "content": prompt}
        ],
        "temperature": 0.5,
        "max_tokens": 500
    }

    try:
        response = requests.post(HIERARCHY_API_ENDPOINT, headers=headers, json=payload, timeout=45)
        response.raise_for_status()
        api_response_data = response.json()
        generated_text = api_response_data['choices'][0]['message']['content'].strip()

        # Basic validation and cleanup
        if generated_text.startswith('[') and generated_text.endswith(']'):
             # Attempt to load to ensure it's valid JSON
             json.loads(generated_text)
             return generated_text
        else:
            # Try to extract JSON if wrapped in text
            start = generated_text.find('[')
            end = generated_text.rfind(']')
            if start != -1 and end != -1 and start < end:
                potential_json = generated_text[start:end+1]
                try:
                    json.loads(potential_json) # Validate
                    print("Warning: Extracted JSON from potentially noisy AI response.")
                    return potential_json
                except json.JSONDecodeError:
                    pass # Fall through if extraction fails

            print(f"Error: AI response was not a valid JSON array. Response:\n{generated_text}")
            return json.dumps({"error": "AI response was not a valid JSON array.", "raw_response": generated_text})

    except requests.exceptions.RequestException as req_err:
        print(f"Error during API request for hierarchy: {req_err}")
        return json.dumps({"error": f"API request failed: {req_err}"})
    except (KeyError, IndexError) as key_err:
         print(f"Error: Unexpected API response structure for hierarchy. Error: {key_err}. Response:\n{api_response_data}")
         return json.dumps({"error": f"Unexpected API response structure: {key_err}", "raw_response": api_response_data})
    except json.JSONDecodeError as json_err:
            # This handles cases where the AI *claims* it's JSON but isn't
            print(f"Error: AI response was not valid JSON after basic checks. Error: {json_err}. Response:\n{generated_text}")
            return json.dumps({"error": f"AI response was not valid JSON: {json_err}", "raw_response": generated_text})
    except Exception as e:
        print(f"An unexpected error occurred during hierarchy generation: {e}")
        traceback.print_exc()
        return json.dumps({"error": f"An unexpected error occurred: {e}"})


# --- Custom WebSocket Callback Handler (Keep As Is) ---
class WebSocketCallbackHandler(BaseCallbackHandler):
    """
    LangChain Callback Handler that emits messages via SocketIO,
    tracks task I/O, cumulative agent token usage, and per-task token usage.
    Includes enhanced debugging and error handling within callbacks.
    """
    def __init__(self, socketio_instance, run_id: str):
        print(f"[Callback Handler {run_id}] Initialized.") # DEBUG PRINT
        self.socketio = socketio_instance
        self.run_id = run_id
        self.agent_token_usage: Dict[str, Dict[str, int]] = {}
        self.task_io_log: List[Dict[str, Any]] = []
        self._current_agent_name: Optional[str] = None
        self._current_task_description: Optional[str] = None
        self._current_task_tokens: Dict[str, int] = self._reset_task_token_counter()

    def _reset_task_token_counter(self) -> Dict[str, int]:
        return {'total_tokens': 0, 'prompt_tokens': 0, 'completion_tokens': 0}

    def _emit_log(self, event_type: str, data: Dict[str, Any]):
        agent_name_context = data.get("agent_name") or self._current_agent_name
        task_desc = data.get("task_description", None) or self._current_task_description
        log_prefix = f"Run({self.run_id})"
        if agent_name_context: log_prefix += f" Agent({agent_name_context})"
        if task_desc: log_prefix += f" Task({task_desc[:30]}...)"
        payload = { "type": event_type, "run_id": self.run_id, "log_prefix": log_prefix, "data": data }
        try:
            self.socketio.emit('log_update', payload, room=self.run_id)
            # print(f"[Callback Handler {self.run_id}] Emitted log: {event_type}") # Optional: Verbose log emission
        except Exception as e:
            print(f"[Callback Handler {self.run_id}] ERROR emitting log '{event_type}': {e}")
            traceback.print_exc() # Print detailed error for emit failure

    def on_llm_start(
        self, serialized: Dict[str, Any], prompts: List[str], **kwargs: Any
    ) -> None:
        # print(f"[Callback Handler {self.run_id}] DEBUG: on_llm_start triggered. Current Agent: {self._current_agent_name}, Current Task: {self._current_task_description}") # DEBUG PRINT
        try:
            self._emit_log("llm_start", {
                "agent_name": self._current_agent_name,
                "task_description": self._current_task_description,
                "prompts_summary": [p[:100]+"..." for p in prompts]
            })
        except Exception as e:
            print(f"[Callback Handler {self.run_id}] ERROR in on_llm_start: {e}")
            traceback.print_exc() # Print detailed error

    def on_llm_end(self, response: LLMResult, **kwargs: Any) -> None:
        # print(f"[Callback Handler {self.run_id}] DEBUG: on_llm_end triggered. Current Agent: {self._current_agent_name}, Current Task: {self._current_task_description}") # DEBUG PRINT
        # print(f"[Callback Handler {self.run_id}] DEBUG: LLM Output: {response.llm_output}") # DEBUG PRINT - Check for token_usage here
        try:
            token_usage = {}
            llm_output_data = response.llm_output or {}
            if 'token_usage' in llm_output_data:
                raw_usage = llm_output_data['token_usage']
                token_usage = {
                    'total_tokens': int(raw_usage.get('total_tokens', 0)),
                    'prompt_tokens': int(raw_usage.get('prompt_tokens', 0)),
                    'completion_tokens': int(raw_usage.get('completion_tokens', 0)),
                }
                # print(f"[Callback Handler {self.run_id}] DEBUG: Parsed token_usage: {token_usage}") # DEBUG PRINT
            else:
                 print(f"[Callback Handler {self.run_id}] WARNING: 'token_usage' not found in llm_output.") # DEBUG WARNING

            # Accumulate for TASK
            if token_usage and self._current_task_description:
                self._current_task_tokens['total_tokens'] += token_usage.get('total_tokens', 0)
                self._current_task_tokens['prompt_tokens'] += token_usage.get('prompt_tokens', 0)
                self._current_task_tokens['completion_tokens'] += token_usage.get('completion_tokens', 0)
                # print(f"[Callback Handler {self.run_id}] DEBUG: Accumulated task tokens: {self._current_task_tokens}") # DEBUG PRINT
            elif token_usage:
                 print(f"[Callback Handler {self.run_id}] DEBUG: Token usage found but no current task description set.") # DEBUG PRINT

            # Accumulate for AGENT
            if self._current_agent_name and token_usage:
                agent_usage = self.agent_token_usage.setdefault(self._current_agent_name, self._reset_task_token_counter()) # Use reset helper for consistency
                agent_usage['total_tokens'] += token_usage.get('total_tokens', 0)
                agent_usage['prompt_tokens'] += token_usage.get('prompt_tokens', 0)
                agent_usage['completion_tokens'] += token_usage.get('completion_tokens', 0)
                # print(f"[Callback Handler {self.run_id}] DEBUG: Accumulated agent '{self._current_agent_name}' tokens: {agent_usage}") # DEBUG PRINT

                # Emit agent usage update
                self._emit_log("agent_usage_update", {
                    "agent_name": self._current_agent_name,
                    "cumulative_usage": self.agent_token_usage[self._current_agent_name]
                })
            elif token_usage:
                print(f"[Callback Handler {self.run_id}] DEBUG: Token usage found but no current agent name set.") # DEBUG PRINT

            generations_summary = [[gen.text[:100] + '...' if len(gen.text) > 100 else gen.text
                                    for gen in gen_list]
                                   for gen_list in response.generations]
            self._emit_log("llm_end", {
                "agent_name": self._current_agent_name,
                "task_description": self._current_task_description,
                "token_usage_for_call": token_usage,
                "cumulative_agent_usage": self.agent_token_usage.get(self._current_agent_name, {}),
                "accumulated_task_usage": self._current_task_tokens if self._current_task_description else {},
                "generations_summary": generations_summary
            })

        except Exception as e:
            print(f"[Callback Handler {self.run_id}] ERROR in on_llm_end: {e}")
            traceback.print_exc() # Print detailed error

    def on_task_start( self, task: CrewTask, **kwargs: Any ) -> Any:
        # print(f"\n[Callback Handler {self.run_id}] DEBUG: ****** on_task_start triggered ******") # DEBUG PRINT
        # print(f"[Callback Handler {self.run_id}] DEBUG: Task Description: {getattr(task, 'description', 'N/A')}") # DEBUG PRINT
        # print(f"[Callback Handler {self.run_id}] DEBUG: Task Agent Role: {getattr(task.agent, 'role', 'N/A') if task.agent else 'No Agent Object'}") # DEBUG PRINT
        # print(f"[Callback Handler {self.run_id}] DEBUG: Kwargs: {kwargs}") # See if useful info is passed
        try:
            agent_role = "Unknown Agent"
            if task.agent and task.agent.role:
                 agent_role = task.agent.role
            else:
                 print(f"[Callback Handler {self.run_id}] Warning: Task started without agent role: {task.description}")

            self._current_agent_name = agent_role
            self._current_task_description = task.description
            self._current_task_tokens = self._reset_task_token_counter()
            # print(f"[Callback Handler {self.run_id}] DEBUG: Set current_agent='{self._current_agent_name}', current_task='{self._current_task_description}', reset task tokens.") # DEBUG PRINT

            self.agent_token_usage.setdefault(self._current_agent_name, self._reset_task_token_counter())

            input_context_summary = "Context analysis unavailable or empty."
            if task.context:
                context_str = str(task.context)
                input_context_summary = f"Context provided (length: {len(context_str)}, type: {type(task.context).__name__})"


            log_data = {
                "task_description": self._current_task_description,
                "agent_name": self._current_agent_name,
                "input_context_summary": input_context_summary,
            }
            self._emit_log("task_start", log_data)

            # Append to task_io_log
            task_log_entry = {
                "task_description": self._current_task_description,
                "agent_name": self._current_agent_name,
                "input_context_summary": input_context_summary,
                "output": None,
                "token_usage": None
            }
            self.task_io_log.append(task_log_entry)
            # print(f"[Callback Handler {self.run_id}] DEBUG: Appended to task_io_log: {task_log_entry}") # DEBUG PRINT
            # print(f"[Callback Handler {self.run_id}] DEBUG: Current task_io_log length: {len(self.task_io_log)}") # DEBUG PRINT

        except Exception as e:
            print(f"[Callback Handler {self.run_id}] ERROR in on_task_start: {e}")
            traceback.print_exc() # Print detailed error

    def on_task_end( self, task: CrewTask, output: Any, **kwargs: Any ) -> Any:
        # print(f"\n[Callback Handler {self.run_id}] DEBUG: ****** on_task_end triggered ******") # DEBUG PRINT
        # print(f"[Callback Handler {self.run_id}] DEBUG: Task Description: {getattr(task, 'description', 'N/A')}") # DEBUG PRINT
        # print(f"[Callback Handler {self.run_id}] DEBUG: Task Agent Role: {getattr(task.agent, 'role', 'N/A') if task.agent else 'No Agent Object'}") # DEBUG PRINT
        # print(f"[Callback Handler {self.run_id}] DEBUG: Output type: {type(output)}") # DEBUG PRINT
        # print(f"[Callback Handler {self.run_id}] DEBUG: Kwargs: {kwargs}") # See if useful info is passed
        try:
            # Use self._current_agent_name if available, fallback to task.agent.role
            agent_role = self._current_agent_name if self._current_agent_name else "Unknown Agent (End)"
            # Correct agent role if task object seems more reliable
            if task.agent and task.agent.role and task.agent.role != agent_role:
                print(f"[Callback Handler {self.run_id}] Warning: Task end agent role '{task.agent.role}' differs from tracked '{agent_role}' for task: {task.description}. Using task object role.")
                agent_role = task.agent.role

            final_task_tokens = self._current_task_tokens.copy()
            # print(f"[Callback Handler {self.run_id}] DEBUG: Final tokens for this task: {final_task_tokens}") # DEBUG PRINT

            print(f"[Callback Handler {self.run_id}] TASK COMPLETE - Task: '{task.description[:50]}...', Agent: {agent_role}, Tokens Used (Task): {final_task_tokens}")

            output_str = str(output)
            output_summary_log = output_str[:200] + '...' if len(output_str) > 200 else output_str

            log_data = {
                "task_description": task.description,
                "agent_name": agent_role,
                "output_summary": output_summary_log,
                "token_usage_for_task": final_task_tokens
            }
            self._emit_log("task_end", log_data)

            entry_updated = False
            # print(f"[Callback Handler {self.run_id}] DEBUG: Searching task_io_log (len {len(self.task_io_log)}) for task '{task.description}' to update.") # DEBUG PRINT
            for i in range(len(self.task_io_log) - 1, -1, -1):
                entry = self.task_io_log[i]
                # Match primarily on description, ensure output/tokens not set yet
                if entry["task_description"] == task.description and entry["output"] is None and entry["token_usage"] is None:
                    # print(f"[Callback Handler {self.run_id}] DEBUG: Found matching task_io_log entry at index {i}.") # DEBUG PRINT
                    entry["output"] = output_str
                    entry["token_usage"] = final_task_tokens
                    if entry["agent_name"] != agent_role:
                        print(f"[Callback Handler {self.run_id}] Notice: Updating agent name in task log from '{entry['agent_name']}' to '{agent_role}' on task end.")
                        entry["agent_name"] = agent_role
                    entry_updated = True
                    break # Stop searching once updated

            if not entry_updated:
                print(f"[Callback Handler {self.run_id}] Warning: Could not find matching task_start entry in task_io_log for task: {task.description}. Appending new.")
                self.task_io_log.append({ # Append even if start missed
                    "task_description": task.description, "agent_name": agent_role,
                    "input_context_summary": "Task start log missing/mismatched",
                    "output": output_str, "token_usage": final_task_tokens
                })
            # print(f"[Callback Handler {self.run_id}] DEBUG: Updated task_io_log length: {len(self.task_io_log)}") # DEBUG PRINT

            # Clear current task/agent trackers
            # print(f"[Callback Handler {self.run_id}] DEBUG: Clearing current task ('{self._current_task_description}') and agent ('{self._current_agent_name}').") # DEBUG PRINT
            self._current_task_description = None
            self._current_agent_name = None
            # Resetting counter isn't strictly necessary as on_task_start does it
            # self._current_task_tokens = self._reset_task_token_counter()

        except Exception as e:
            print(f"[Callback Handler {self.run_id}] ERROR in on_task_end: {e}")
            traceback.print_exc() # Print detailed error

    # --- (Keep get_agent_token_usage and get_task_io_log) ---
    def get_agent_token_usage(self) -> Dict[str, Dict[str, int]]:
        return self.agent_token_usage

    def get_task_io_log(self) -> List[Dict[str, Any]]:
         # print(f"[Callback Handler {self.run_id}] DEBUG: get_task_io_log called. Returning log with {len(self.task_io_log)} entries.") # DEBUG PRINT
         return self.task_io_log


# --- Background Crew Execution Function (MODIFIED) ---
def run_crew_background(task_description: str, run_id: str, socketio_instance: SocketIO):
    """
    Runs the CrewAI process in the background, tracks usage per agent and per task,
    assigns random token rates and calculates costs per agent, and emits updates via SocketIO.
    Includes enhanced debugging.

    Args:
        task_description: The user-provided task for the crew.
        run_id: The unique identifier for this execution run.
        socketio_instance: The Flask-SocketIO instance used for emitting messages.
    """
    print(f"--- Starting background crew run (ID: {run_id}) for task: '{task_description}' ---")
    socketio_instance.emit('log_update', {'type': 'status', 'run_id': run_id, 'data': {'message': 'Crew run starting...'}}, room=run_id)

    callback_handler = WebSocketCallbackHandler(socketio_instance, run_id)

    # --- Check API Key for Crew's LLM ---
    crew_llm_key = os.getenv("OPENAI_API_KEY")
    key_ok, error_msg = check_api_key(crew_llm_key, "CrewAI LLM API Key (OPENAI_API_KEY)")
    if not key_ok:
        error_occurred = f"Configuration Error: {error_msg}"
        print(f"Error (Run ID: {run_id}): {error_occurred}")
        socketio_instance.emit('log_update', {'type': 'error', 'run_id': run_id, 'data': {'message': error_occurred}}, room=run_id)
        # Store error before exiting
        result_data = {
            "run_id": run_id, 
            "task_description": task_description, 
            "agent_hierarchy": None,
            "final_output": None, 
            "task_flow": callback_handler.get_task_io_log(),
            "usage_metrics": None, 
            "agent_token_usage": callback_handler.get_agent_token_usage(),
            "error": error_occurred
        }
        with storage_lock: crew_results_storage[run_id] = result_data
        socketio_instance.emit('run_complete', {'run_id': run_id, 'status': 'error', 'error': error_occurred, 'final_result': result_data}, room=run_id)
        return

    # --- Instantiate LLM with Callback ---
    llm_model_name = os.getenv("CREW_LLM_MODEL", "gpt-4o")
    llm_with_callbacks = None
    try:
        llm_with_callbacks = ChatOpenAI(
            model=llm_model_name,
            openai_api_key=crew_llm_key,
            callbacks=[callback_handler]
        )
        socketio_instance.emit('log_update', {'type': 'status', 'run_id': run_id, 'data': {'message': f'LLM ({llm_model_name}) initialized with callbacks.'}}, room=run_id)
    except Exception as e:
        error_occurred = f"Failed to initialize LLM ({llm_model_name}): {e}"
        print(f"Error (Run ID: {run_id}): {error_occurred}")
        traceback.print_exc()
        socketio_instance.emit('log_update', {'type': 'error', 'run_id': run_id, 'data': {'message': error_occurred}}, room=run_id)
        result_data = {
            "run_id": run_id, 
            "task_description": task_description, 
            "agent_hierarchy": None,
            "final_output": None, 
            "task_flow": callback_handler.get_task_io_log(),
            "usage_metrics": None, 
            "agent_token_usage": callback_handler.get_agent_token_usage(),
            "error": error_occurred
        }
        with storage_lock: crew_results_storage[run_id] = result_data
        socketio_instance.emit('run_complete', {'run_id': run_id, 'status': 'error', 'error': error_occurred, 'final_result': result_data}, room=run_id)
        return

    # --- Generate Hierarchy ---
    socketio_instance.emit('log_update', {'type': 'status', 'run_id': run_id, 'data': {'message': 'Generating agent hierarchy...'}}, room=run_id)
    hierarchy_json_str = create_agent_hierarchy_with_ai(task_description)
    print(hierarchy_json_str)
    hierarchy_data = None
    final_result_raw = None
    crew_output_obj = None
    usage_metrics = None
    error_occurred = None

    try:
        hierarchy_data = json.loads(hierarchy_json_str)
        if isinstance(hierarchy_data, dict) and 'error' in hierarchy_data:
            error_msg = f"Error generating hierarchy: {hierarchy_data.get('error', 'Unknown error')}"
            raw_resp = hierarchy_data.get('raw_response')
            if raw_resp: error_msg += f" Raw Response: {raw_resp}"
            error_occurred = error_msg
            hierarchy_data = None
        elif not isinstance(hierarchy_data, list) or not hierarchy_data:
             error_msg = "Generated hierarchy is not a valid list or is empty."
             error_occurred = error_msg
             hierarchy_data = None
        else:
             socketio_instance.emit('log_update', {'type': 'hierarchy_generated', 'run_id': run_id, 'data': {'hierarchy': hierarchy_data}}, room=run_id)

    except json.JSONDecodeError as e:
        error_msg = f"Error decoding JSON hierarchy: {e}. Received: {hierarchy_json_str}"
        error_occurred = error_msg
        hierarchy_data = None
    except Exception as e:
         error_occurred = f"Unexpected error processing hierarchy: {e}"
         print(f"Error (Run ID: {run_id}): {error_occurred}")
         traceback.print_exc()
         hierarchy_data = None

    if error_occurred:
        print(f"Error (Run ID: {run_id}): Halting run due to hierarchy error: {error_occurred}")
        socketio_instance.emit('log_update', {'type': 'error', 'run_id': run_id, 'data': {'message': error_occurred, 'raw_hierarchy_response': hierarchy_json_str if isinstance(hierarchy_json_str, str) else None}}, room=run_id)
        result_data = {
            "run_id": run_id, 
            "task_description": task_description, 
            "agent_hierarchy": None,
            "final_output": None, 
            "task_flow": callback_handler.get_task_io_log(),
            "usage_metrics": None, 
            "agent_token_usage": callback_handler.get_agent_token_usage(),
            "error": error_occurred
        }
        with storage_lock: crew_results_storage[run_id] = result_data
        socketio_instance.emit('run_complete', {'run_id': run_id, 'status': 'error', 'error': error_occurred, 'final_result': result_data}, room=run_id)
        return

    # --- Create Agents and Tasks ---
    agents: List[Agent] = []
    tasks: List[CrewTask] = []
    if hierarchy_data:
        socketio_instance.emit('log_update', {'type': 'status', 'run_id': run_id, 'data': {'message': f'Creating {len(hierarchy_data)} agents and tasks...'}}, room=run_id)

        # if llm_with_callbacks:
        #      print(f"[Crew Run {run_id}] DEBUG: LLM instance (before Agent loop) ID: {id(llm_with_callbacks)}, Callbacks: {llm_with_callbacks.callbacks}")
        # else:
        #      print(f"[Crew Run {run_id}] DEBUG: LLM instance (before Agent loop) is None!")

        for i, agent_info in enumerate(hierarchy_data):
            try:
                if not isinstance(agent_info, dict):
                     raise TypeError(f"Agent data item {i} is not a dictionary: {agent_info}")
                agent_name = agent_info.get('agent_name')
                description = agent_info.get('description')
                if not agent_name or not isinstance(agent_name, str):
                    raise KeyError(f"Missing or invalid 'agent_name' in agent data item {i}: {agent_info}")
                if not description or not isinstance(description, str):
                     raise KeyError(f"Missing or invalid 'description' in agent data item {i}: {agent_info}")

                agent_role = agent_name.replace('_', ' ')
                # print(f"[Crew Run {run_id}] DEBUG: Assigning LLM instance ID {id(llm_with_callbacks)} to Agent '{agent_role}'")

                agent = Agent(
                    role=agent_role,
                    goal=f"Fulfill role: {description}, contributing to the overall task: '{task_description}'",
                    backstory=(
                        f"You are an AI agent named {agent_role}. Your expertise lies in {description}. "
                        f"You are part of a team working sequentially on the task: '{task_description}'. Focus strictly on your defined role "
                        f"and ensure your output is clear and directly usable by the next agent or as a final result component."
                    ),
                    verbose=False,
                    allow_delegation=False,
                    llm=llm_with_callbacks,
                    max_iter=15
                )
                agents.append(agent)

                task = CrewTask(
                    description=(
                        f"Execute your role as {agent.role}. Your specific focus is: {description}. "
                        f"Use the context provided (output from the previous agent, if any) to perform your part of the overall goal: '{task_description}'. "
                        f"Your output must be self-contained and ready for the next step."
                    ),
                    expected_output=(
                        f"A clear, concise, and well-formatted result from your work on '{description}'. "
                        f"This output should directly address your assigned part of the task and be suitable for use by subsequent agents or as a final output component."
                    ),
                    agent=agent,
                    async_execution=False
                )
                tasks.append(task)
                socketio_instance.emit('log_update', {
                    'type': 'agent_created', 'run_id': run_id,
                    'data': {'agent_name': agent.role, 'task_description': task.description}
                    }, room=run_id)

            except (KeyError, TypeError) as e:
                error_msg = f"Error processing agent data item {i}: {e}. Agent Info: {agent_info}. Skipping this agent/task."
                print(f"Warning (Run ID: {run_id}): {error_msg}")
                socketio_instance.emit('log_update', {'type': 'warning', 'run_id': run_id, 'data': {'message': error_msg}}, room=run_id)
            except Exception as e:
                 error_msg = f"Unexpected error creating agent/task for {agent_info.get('agent_name', 'Unknown')}: {e}"
                 print(f"Error (Run ID: {run_id}): {error_msg}")
                 traceback.print_exc()
                 socketio_instance.emit('log_update', {'type': 'warning', 'run_id': run_id, 'data': {'message': f"Skipping agent {agent_info.get('agent_name', 'Unknown')} due to error: {e}"}}, room=run_id)

    # --- Run Crew ---
    if agents and tasks:
        socketio_instance.emit('log_update', {'type': 'status', 'run_id': run_id, 'data': {'message': f'Assembling and kicking off the crew with {len(agents)} agents and {len(tasks)} tasks...'}}, room=run_id)
        try:
            # print(f"[Crew Run {run_id}] DEBUG: Creating Crew object with {len(agents)} agents, {len(tasks)} tasks.")
            crew = Crew(
                agents=agents,
                tasks=tasks,
                process=Process.sequential,
                verbose=False, # Boolean True/False expected
                callbacks=[callback_handler]
            )

            # print(f"[Crew Run {run_id}] DEBUG: === Kicking off Crew ===")
            crew_output_obj = crew.kickoff(inputs=None)
            # print(f"[Crew Run {run_id}] DEBUG: === Crew kickoff finished ===")

            if crew_output_obj is not None:
                 if isinstance(crew_output_obj, str):
                      final_result_raw = crew_output_obj
                 elif hasattr(crew_output_obj, 'raw') and crew_output_obj.raw is not None:
                      final_result_raw = crew_output_obj.raw
                 elif hasattr(crew_output_obj, 'result') and crew_output_obj.result is not None:
                       final_result_raw = crew_output_obj.result
                 else:
                      final_result_raw = str(crew_output_obj)

                 if hasattr(crew_output_obj, 'token_usage') and crew_output_obj.token_usage:
                      usage_metrics = crew_output_obj.token_usage
                 elif hasattr(crew, 'usage_metrics'):
                      usage_metrics = crew.usage_metrics
                 else:
                     usage_metrics = None
            else:
                 final_result_raw = None
                 usage_metrics = getattr(crew, 'usage_metrics', None)

            socketio_instance.emit('log_update', {'type': 'status', 'run_id': run_id, 'data': {'message': 'Crew execution finished.'}}, room=run_id)

        except Exception as e:
            error_msg = f"Error During Crew Execution: {e}"
            print(f"\n--- Error (Run ID: {run_id}): {error_msg} ---")
            traceback.print_exc()
            error_occurred = error_msg
            final_result_raw = None
            try:
                if 'crew' in locals() and hasattr(crew, 'usage_metrics'):
                    usage_metrics = crew.usage_metrics
                else:
                    usage_metrics = None
            except Exception as usage_err:
                 print(f"Warning (Run ID: {run_id}): Could not retrieve usage metrics after crew execution error: {usage_err}")
                 usage_metrics = None
            socketio_instance.emit('log_update', {'type': 'error', 'run_id': run_id, 'data': {'message': error_msg, 'traceback': traceback.format_exc()}}, room=run_id)

    elif not error_occurred:
        error_occurred = "Crew could not run: No valid agents or tasks were created from the hierarchy."
        print(f"Error (Run ID: {run_id}): {error_occurred}")
        socketio_instance.emit('log_update', {'type': 'error', 'run_id': run_id, 'data': {'message': error_occurred}}, room=run_id)

    # --- Final Processing & Storage ---
    agent_usage_data = callback_handler.get_agent_token_usage()
    task_flow_log = callback_handler.get_task_io_log()

    # --- >>> ADD RANDOM RATES AND COSTS <<< ---
    # Iterate through the collected agent usage and add pricing info
    for agent_name, usage_details in agent_usage_data.items():
        # Generate a random rate (e.g., USD per 1 Million tokens)
        # Adjust the range (0.5 to 10.0) as needed for typical token costs
        random_rate_usd_per_million = round(random.uniform(0.5, 10.0), 2)

        # Get total tokens used by this agent
        total_tokens = usage_details.get('total_tokens', 0)

        # Calculate estimated cost
        estimated_cost_usd = (total_tokens / 1_000_000) * random_rate_usd_per_million

        # Add the rate and cost to the agent's usage dictionary
        usage_details['token_rate_usd_per_million'] = random_rate_usd_per_million
        usage_details['estimated_cost_usd'] = round(estimated_cost_usd, 6) # Round cost to 6 decimal places

    # --- >>> END ADD RANDOM RATES AND COSTS <<< ---

    # Prepare the final result structure
    result_data = {
        "run_id": run_id,
        "task_description": task_description,
        "agent_hierarchy": hierarchy_data,
        "final_output": final_result_raw,
        "task_flow": task_flow_log,
        "usage_metrics": None, # Placeholder for total crew metrics
        "agent_token_usage": agent_usage_data, # <<< NOW INCLUDES rates/costs >>>
        "error": error_occurred,
    }

    # Safely process total usage_metrics
    processed_total_metrics = None
    if usage_metrics:
         if isinstance(usage_metrics, dict):
             processed_total_metrics = {
                 'total_tokens': int(usage_metrics.get('total_tokens', 0)),
                 'prompt_tokens': int(usage_metrics.get('prompt_tokens', 0)),
                 'completion_tokens': int(usage_metrics.get('completion_tokens', 0)),
                 'successful_requests': int(usage_metrics.get('successful_requests', 0))
             }
         else:
             try:
                 processed_total_metrics = {}
                 expected_attrs = ['total_tokens', 'prompt_tokens', 'completion_tokens', 'successful_requests']
                 for attr in expected_attrs:
                     if hasattr(usage_metrics, attr):
                         value = getattr(usage_metrics, attr)
                         processed_total_metrics[attr] = int(value) if value is not None else 0
                 if not processed_total_metrics and hasattr(usage_metrics, '__dict__'):
                    processed_total_metrics = {k: int(v) if isinstance(v, (int, float)) else str(v)
                                               for k, v in usage_metrics.__dict__.items()
                                               if k in expected_attrs}
             except (TypeError, ValueError) as conv_err:
                 print(f"Warning (Run ID: {run_id}): Could not convert total usage_metrics object: {conv_err}")
                 processed_total_metrics = {'error': 'Could not parse usage object', 'raw': str(usage_metrics)}

    result_data['usage_metrics'] = processed_total_metrics

    # Log Final Summary (will use the modified log_final_summary below)
    log_final_summary(run_id, result_data)

    # Store results in memory
    with storage_lock:
        crew_results_storage[run_id] = result_data
        print(f"--- Results stored under key (run_id): {run_id} ---")

    # Emit Final Status via WebSocket
    final_status = 'error' if error_occurred else 'success'
    socketio_instance.emit('run_complete', {
        'run_id': run_id,
        'status': final_status,
        'error': error_occurred,
        'final_result': result_data # Send the complete result with pricing
    }, room=run_id)

    print(f"--- Background crew run finished (ID: {run_id}) ---")

# --- Final Summary Logging Function (MODIFIED) ---
def log_final_summary(run_id, result_data):
    """Helper function to print a detailed summary of the run results,
       including token rates and costs per agent."""
    print(f"\n{'=' * 40}")
    print(f"FINAL SUMMARY FOR RUN: {run_id}")
    print(f"{'=' * 40}")

    print(f"Task Description: {result_data.get('task_description')}")
    print(f"Status: {'Error' if result_data.get('error') else 'Success'}")
    if result_data.get('error'):
        print(f"Error Message: {result_data['error']}")

    print(f"\n--- Final Output ---")
    print(result_data.get('final_output', 'N/A'))

    print(f"\n--- Total Usage Metrics (from crew) ---")
    print(result_data.get('usage_metrics', 'N/A'))

    # Print Agent Cumulative Usage Breakdown (with pricing)
    agent_token_usage = result_data.get('agent_token_usage', {})
    if agent_token_usage:
        print("\n--- Agent Cumulative Token Usage & Estimated Cost (from callbacks) ---")
        # Adjusted header width
        print("-" * 105)
        print(f"{'AGENT NAME':<30} {'PROMPT':<10} {'COMPLETION':<15} {'TOTAL':<10} {'RATE (USD/M)':<15} {'EST. COST (USD)':<15}")
        print("-" * 105)
        total_agent_prompt = 0
        total_agent_completion = 0
        total_agent_overall = 0
        total_estimated_cost = 0.0
        for agent_name, usage in agent_token_usage.items():
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)
            rate = usage.get('token_rate_usd_per_million', 'N/A')
            cost = usage.get('estimated_cost_usd', 'N/A')

            total_agent_prompt += prompt_tokens
            total_agent_completion += completion_tokens
            total_agent_overall += total_tokens
            if isinstance(cost, (int, float)):
                total_estimated_cost += cost

            # Format rate and cost for printing
            rate_str = f"${rate:.2f}" if isinstance(rate, (int, float)) else "N/A"
            cost_str = f"${cost:.6f}" if isinstance(cost, (int, float)) else "N/A"

            print(f"{agent_name:<30} {prompt_tokens:<10} {completion_tokens:<15} {total_tokens:<10} {rate_str:<15} {cost_str:<15}")
        print("-" * 105)
        print(f"{'TOTAL (Agents)':<30} {total_agent_prompt:<10} {total_agent_completion:<15} {total_agent_overall:<10} {'':<15} ${total_estimated_cost:.6f}{'':<9}") # Adjusted spacing
    else:
        print("\n--- Agent Cumulative Token Usage & Estimated Cost (from callbacks): Not Available ---")

    # Print Task Usage Breakdown (remains the same)
    task_flow = result_data.get('task_flow', [])
    if task_flow:
        print("\n--- Task Token Usage (from callbacks) ---")
        print("-" * 90)
        print(f"{'TASK DESCRIPTION':<40} {'AGENT':<20} {'PROMPT':<10} {'COMPLETION':<15} {'TOTAL':<10}")
        print("-" * 90)
        total_task_prompt = 0
        total_task_completion = 0
        total_task_overall = 0
        for task_item in task_flow:
            desc = task_item.get('task_description', 'N/A')[:38] + ".." if len(task_item.get('task_description', 'N/A')) > 40 else task_item.get('task_description', 'N/A')
            agent = task_item.get('agent_name', 'N/A')[:18] + ".." if len(task_item.get('agent_name', 'N/A')) > 20 else task_item.get('agent_name', 'N/A')
            usage = task_item.get('token_usage') or {'prompt_tokens': 0, 'completion_tokens': 0, 'total_tokens': 0}
            prompt_tokens = usage.get('prompt_tokens', 0)
            completion_tokens = usage.get('completion_tokens', 0)
            total_tokens = usage.get('total_tokens', 0)
            total_task_prompt += prompt_tokens
            total_task_completion += completion_tokens
            total_task_overall += total_tokens
            print(f"{desc:<40} {agent:<20} {prompt_tokens:<10} {completion_tokens:<15} {total_tokens:<10}")
        print("-" * 90)
        print(f"{'TOTAL (Tasks)':<61} {total_task_prompt:<10} {total_task_completion:<15} {total_task_overall:<10}")
    else:
         print("\n--- Task Token Usage (from callbacks): Not Available ---")

    print(f"{'=' * 40}\n")


# --- API Endpoints (Keep As Is) ---

@app.route('/', methods=['GET'])
def health_check():
    """Basic health check endpoint."""
    return jsonify({"status": "ok", "message": "CrewAI API server is running"}), 200

@app.route('/run', methods=['POST'])
def run_crew_endpoint():
    """
    API endpoint to trigger a crew run asynchronously.
    Expects JSON: {"task_description": "..."}
    Returns JSON: {"run_id": "..."}
    """
    if not request.is_json:
        return jsonify({"error": "Request must be JSON"}), 400

    data = request.get_json()
    task_description = data.get('task_description')

    if not task_description or not isinstance(task_description, str) or not task_description.strip():
        return jsonify({"error": "Missing or invalid 'task_description'"}), 400

    task_description = re.sub(r'[^\w\s.,!?-]', '', task_description[:1500]).strip()

    if not task_description:
        return jsonify({"error": "Task description is empty after sanitization"}), 400

    run_id = str(uuid.uuid4())

    print(f"--- Received API request (Run ID: {run_id}) for task: '{task_description}' ---")
    print(f"--- Starting background task for run ID: {run_id} ---")

    try:
        socketio.start_background_task(
            run_crew_background,
            task_description=task_description,
            run_id=run_id,
            socketio_instance=socketio
        )
    except Exception as bg_task_err:
         print(f"CRITICAL: Failed to start background task for run {run_id}: {bg_task_err}")
         traceback.print_exc()
         return jsonify({"error": "Failed to initiate background processing", "run_id": run_id}), 500

    return jsonify({"run_id": run_id}), 202
# --- Results Endpoints (Keep As Is) ---

@app.route('/results', methods=['GET'])
def get_results_list():
    """API endpoint to list available result run_ids."""
    with storage_lock:
        keys = list(crew_results_storage.keys())
    return jsonify({"available_run_ids": keys}), 200


@app.route('/results/<run_id>', methods=['GET'])
def get_result_detail(run_id):
    """API endpoint to get detailed results for a specific run_id."""
    if not isinstance(run_id, str) or not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', run_id):
         return jsonify({"error": "Invalid run_id format"}), 400

    with storage_lock:
        result = crew_results_storage.get(run_id)
        if result:
            import copy
            result_copy = copy.deepcopy(result)
        else:
            result_copy = None

    if result_copy:
        # The result_copy already contains the pricing info in agent_token_usage
        return jsonify(result_copy), 200
    else:
        return jsonify({"error": f"Results not found for run_id: {run_id}. It might still be running or failed to start."}), 404


# --- WebSocket Event Handlers (Keep As Is) ---

@socketio.on('connect')
def handle_connect():
    """Called when a client connects to the WebSocket."""
    print(f"Client connected: {request.sid}")

@socketio.on('disconnect')
def handle_disconnect():
    """Called when a client disconnects."""
    print(f"Client disconnected: {request.sid}")

@socketio.on('join_room')
def handle_join_room(data):
    """Called when a client wants to join a room to receive logs for a specific run."""
    if not isinstance(data, dict):
        print(f"Client {request.sid} sent invalid join data type: {type(data)}")
        emit('error', {'message': 'Invalid data format. Send {"run_id": "your_run_id"}.'})
        return

    run_id = data.get('run_id')
    if not run_id or not isinstance(run_id, str):
        print(f"Client {request.sid} tried to join room without valid run_id.")
        emit('error', {'message': 'run_id must be provided as a string.'})
        return

    if not re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', run_id):
         print(f"Client {request.sid} tried to join invalid room format: {run_id}")
         emit('error', {'message': 'Invalid run_id format provided.'})
         return

    join_room(run_id)
    print(f"Client {request.sid} joined room: {run_id}")
    emit('joined_room', {'run_id': run_id, 'message': f'Successfully joined room {run_id}. Waiting for logs...'})

    existing_result = None
    with storage_lock:
        result_in_storage = crew_results_storage.get(run_id)
        if result_in_storage:
             import copy
             existing_result = copy.deepcopy(result_in_storage)

    if existing_result:
         status = 'error' if existing_result.get('error') else 'success'
         print(f"Sending existing results for run {run_id} to client {request.sid}")
         emit('run_complete', {
              'run_id': run_id,
              'status': status,
              'error': existing_result.get('error'),
              'final_result': existing_result
              })

@socketio.on('leave_room')
def handle_leave_room(data):
    """Called when a client wants to explicitly leave a room."""
    if not isinstance(data, dict):
        print(f"Client {request.sid} sent invalid leave data type: {type(data)}")
        emit('error', {'message': 'Invalid data format. Send {"run_id": "your_run_id"}.'})
        return

    run_id = data.get('run_id')
    if run_id and isinstance(run_id, str) and re.fullmatch(r'[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}', run_id):
        leave_room(run_id)
        print(f"Client {request.sid} left room: {run_id}")
        emit('left_room', {'run_id': run_id, 'message': f'Successfully left room {run_id}.'})
    else:
        print(f"Client {request.sid} tried to leave room with invalid/missing run_id.")
        emit('error', {'message': 'Valid run_id must be provided to leave a room.'})


# --- Main Execution Block (Keep As Is) ---
if __name__ == "__main__":
    # Check essential API key on startup
    key_ok, error_message = check_api_key(os.getenv("OPENAI_API_KEY"), "OPENAI_API_KEY")
    if not key_ok:
        print(f"CRITICAL ERROR: Cannot start server - {error_message}. Ensure OPENAI_API_KEY is set in your .env file or environment.")
        exit(1)
    else:
        print("OPENAI_API_KEY found.")

    # Check optional Flask Secret Key
    if not os.getenv('FLASK_SECRET_KEY'):
        print("Warning: FLASK_SECRET_KEY not set. Using default (unsafe for production).")

    print("Starting Flask-SocketIO server...")

    server_port = int(os.getenv("PORT", 8080))
    debug_mode = os.getenv("FLASK_DEBUG", "False").lower() in ["true", "1", "t"]

    print(f" * Running on http://0.0.0.0:{server_port}/ (Press CTRL+C to quit)")
    print(f" * Debug mode: {'on' if debug_mode else 'off'}")
    print(f" * PORT environment variable: {os.getenv('PORT', 'Not set')}")

    try:
        # This is the preferred way for running in production with gunicorn
        # gunicorn will handle the app directly when we use the startCommand in render.yaml
        # This block is just for local development
        if not os.getenv("RENDER"):
            socketio.run(
                app,
                debug=debug_mode,
                host='0.0.0.0',
                port=server_port,
                allow_unsafe_werkzeug=True
                )
    except KeyboardInterrupt:
        print("Server stopped.")
    except Exception as run_err:
         print(f"Failed to run the server: {run_err}")
         traceback.print_exc()
