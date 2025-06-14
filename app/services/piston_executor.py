import requests
import logging
from app.utils.testcase_utils import dict_to_stdin, normalize_output, compare_outputs
from typing import Any, Dict # Added type hints

logger = logging.getLogger(__name__)

# Piston API endpoint
PISTON_API_URL = "https://emkc.org/api/v2/piston/execute"
# PISTON_API_URL = os.getenv("PISTON_API_URL", "https://emkc.org/api/v2/piston/execute") # Alternative if configurable

def get_filename_for_language(language: str) -> str:
    """Get appropriate filename based on language.
       Piston generally uses 'main.<ext>' or specific names for some languages.
       The exact name doesn't matter much as long as content is there.
    """
    filename_map = {
        "python": "main.py",
        "python3": "main.py", # Piston often uses 'python' for Python 3
        "java": "Main.java", # Java class name must match filename for public class
        "c++": "main.cpp", # Common alias for cpp
        "cpp": "main.cpp",
        "c": "main.c",
        "javascript": "main.js",
        "typescript": "main.ts",
        "go": "main.go",
        "rust": "main.rs",
        "csharp": "Main.cs", # C# often uses Main.cs with a Main method
        "ruby": "main.rb",
        "swift": "main.swift",
        "kotlin": "main.kt",
    }
    # Default if language not in map, Piston might infer or use first file
    return filename_map.get(language.lower(), f"source.{language}")


def execute_on_piston(
    code: str, 
    language: str, 
    version: str, 
    input_dict: Any, # Can be dict, list, str, int, float
    expected_output: Any
) -> Dict[str, Any]:
    try:
        # Step 1: Convert input_dict (which can be any JSON-like structure) to stdin string
        logger.info(f"Input value before dict_to_stdin: {input_dict} (type: {type(input_dict)})")
        stdin_str = dict_to_stdin(input_dict)
        logger.info(f"Generated stdin for Piston: {repr(stdin_str)}")
        
        # Step 2: Get appropriate filename for the language
        filename = get_filename_for_language(language)
        logger.info(f"Using filename: {filename} for language: {language}, version: {version}")
        
        # Step 3: Prepare payload for Piston API
        payload = {
            "language": language,
            "version": version, # Ensure this version is supported by Piston for the language
            "files": [{"name": filename, "content": code}],
            "stdin": stdin_str,
            # "args": [], # Command line arguments if needed
            # "compile_timeout": 10000, # ms
            # "run_timeout": 3000, # ms
            # "compile_memory_limit": -1, # KB
            # "run_memory_limit": -1, # KB
        }
        
        # Step 4: Execute request
        logger.info(f"Sending request to Piston API ({PISTON_API_URL})")
        # logger.debug(f"Piston API payload: {json.dumps(payload, indent=2)}") # Be careful with logging full code

        response = requests.post(
            url=PISTON_API_URL,
            headers={"Content-Type": "application/json"},
            json=payload,
            timeout=20  # Increased timeout (Piston can be slow)
        )
        
        # Step 5: Handle response
        response.raise_for_status() # Raises HTTPError for bad responses (4XX or 5XX)
        
        result = response.json()
        logger.info(f"Piston API raw response: {result}")
        
        # Piston response structure:
        # {
        #   "language": "python", "version": "3.10.0",
        #   "run": {"stdout": "...", "stderr": "...", "code": 0, "signal": null, "output": "..."},
        #   "compile": {"stdout": "...", "stderr": "...", "code": 0, "signal": null, "output": "..."} (optional)
        # }

        compile_stage = result.get("compile")
        run_stage = result.get("run")

        if not run_stage: # Should always be present if request was successful
            logger.error(f"Piston response missing 'run' stage: {result}")
            return {
                "compile_error": "Invalid Piston response: Missing 'run' stage.",
                "runtime_error": None, "stdout": "", "stderr": "", "passed": False
            }

        # Check for compilation errors (if compile stage exists and failed)
        if compile_stage and compile_stage.get("code", 0) != 0:
            compile_stderr = compile_stage.get("stderr", "").strip()
            compile_stdout = compile_stage.get("stdout", "").strip() # Less common but possible
            error_message = compile_stderr or compile_stdout or "Compilation failed (no specific error message)."
            logger.warning(f"Compilation failed: {error_message}")
            return {
                "compile_error": error_message,
                "runtime_error": None,
                "stdout": compile_stdout, # Include stdout from compile if any
                "stderr": compile_stderr, # Main error message
                "passed": False
            }
        
        # Get runtime results
        actual_stdout = run_stage.get("stdout", "").strip()
        actual_stderr = run_stage.get("stderr", "").strip()
        exit_code = run_stage.get("code", 0) # Exit code of the program
        # signal = run_stage.get("signal") # e.g., "SIGTERM", "SIGKILL" if terminated by signal

        logger.info(f"Execution results - stdout: {repr(actual_stdout)}, stderr: {repr(actual_stderr)}, exit_code: {exit_code}")
        
        # Check for runtime errors (non-zero exit code or stderr content)
        # Some programs might print to stderr for non-fatal warnings, so exit_code is primary.
        if exit_code != 0:
            runtime_error_message = actual_stderr or f"Runtime error (exit code: {exit_code})"
            logger.warning(f"Runtime error: {runtime_error_message}")
            return {
                "compile_error": None,
                "runtime_error": runtime_error_message,
                "stdout": actual_stdout,
                "stderr": actual_stderr, # Keep stderr even if it was used for error message
                "passed": False
            }
        # If exit code is 0 but there's significant stderr, it might indicate an issue still,
        # but typically indicates non-fatal warnings. For competitive programming, usually stderr means error.
        # For now, we trust exit_code primarily for runtime error state.

        # Step 6: Compare with expected output
        # `expected_output` is already a Python object (parsed from JSON)
        # `actual_stdout` is a string from Piston. `compare_outputs` handles normalization.
        passed = compare_outputs(actual_stdout, expected_output)
        
        return {
            "compile_error": None,
            "runtime_error": None, # No runtime error if exit_code was 0
            "stdout": actual_stdout,
            "stderr": actual_stderr, # Stderr might contain non-fatal warnings or debug info
            "passed": passed,
            "normalized_expected": normalize_output(expected_output), # For debugging/logging
            "normalized_actual": normalize_output(actual_stdout)   # For debugging/logging
        }
        
    except requests.exceptions.HTTPError as e:
        # Errors from Piston API itself (e.g. 400 for bad language, 500 for Piston internal error)
        error_body = e.response.text
        logger.error(f"Piston API HTTP error: {e.response.status_code} - {error_body}", exc_info=True)
        # Try to parse Piston's error message if it's JSON
        try:
            piston_error_json = e.response.json()
            message = piston_error_json.get("message", error_body)
        except ValueError: # json.JSONDecodeError
            message = error_body
        
        return {
            "compile_error": f"Piston API error ({e.response.status_code}): {message}",
            "runtime_error": None, "stdout": "", "stderr": message, "passed": False
        }
    except requests.exceptions.RequestException as e: # Timeout, ConnectionError, etc.
        logger.error(f"Network error calling Piston API: {str(e)}", exc_info=True)
        return {
            "compile_error": f"Network error connecting to Piston: {str(e)}",
            "runtime_error": None, "stdout": "", "stderr": str(e), "passed": False
        }
    except Exception as e: # Catch-all for other unexpected errors
        logger.error(f"Unexpected error in execute_on_piston: {str(e)}", exc_info=True)
        return {
            "compile_error": f"Unexpected error during execution: {str(e)}",
            "runtime_error": None, "stdout": "", "stderr": str(e), "passed": False
        }