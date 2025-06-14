import json
import ast
import logging
from typing import Any, Dict, List # Correct: Any is imported

logger = logging.getLogger(__name__)

def load_test_case(path: str) -> Dict[str, Any]:
    """Load test case from JSON file.
    This function might be used for local testing or legacy support
    but is not central to the DB-based test case flow.
    """
    try:
        with open(path, 'r') as file:
            test_case_data: Dict[str, Any] = json.load(file)
            logger.info(f"Test case loaded from {path}")
            return test_case_data 
    except FileNotFoundError:
        logger.error(f"Test case file not found at {path}", exc_info=True)
        raise
    except json.JSONDecodeError as e:
        logger.error(f"Error decoding JSON from {path}: {str(e)}", exc_info=True)
        raise
    except Exception as e:
        logger.error(f"Error loading test case from {path}: {str(e)}", exc_info=True)
        raise

def dict_to_stdin(input_value: Any) -> str: # Correct: Use capital 'A' for the type hint
    """Convert input value (dict, list, str, int, float) to stdin string format"""
    if isinstance(input_value, str):
        return input_value if input_value.endswith('\n') else input_value + "\n"

    if not isinstance(input_value, dict):
        if isinstance(input_value, list):
            return " ".join(map(str, input_value)) + "\n"
        return str(input_value) + "\n"

    stdin_lines: List[str] = [] 
    try:
        # Iterating over input_value.items() where value can be of mixed types.
        # Pylance might infer 'value' as 'object' or 'Unknown'.
        # This is generally fine as isinstance checks handle the types.
        for key, value in input_value.items(): 
            if isinstance(value, list):
                if key.lower() in ['arr', 'array', 'nums', 'numbers', 'list', 'elements']:
                    stdin_lines.append(str(len(value))) 
                    stdin_lines.append(" ".join(map(str, value))) 
                else: 
                    stdin_lines.append(" ".join(map(str, value)))
            elif isinstance(value, dict):
                stdin_lines.append(json.dumps(value))
            else: 
                stdin_lines.append(str(value))
        
        result = "\n".join(stdin_lines) + "\n"
        logger.info(f"Generated stdin from dict: {repr(result)}")
        return result
        
    except Exception as e:
        logger.error(f"Error converting dict to stdin: {str(e)}", exc_info=True)
        logger.error(f"Input value: {input_value}")
        if isinstance(input_value, dict):
            return "\n".join(str(v) for v in input_value.values()) + "\n"
        return str(input_value) + "\n" 



def normalize_output(output: Any) -> Any:
    if output is None:
        return "" 

    if isinstance(output, str):
        normalized_str = output.strip()
        
        if normalized_str.lower() == "true": 
            return True
        if normalized_str.lower() == "false": 
            return False
        
        # Attempt 1: Try ast.literal_eval for standard Python literals
        try:
            parsed = ast.literal_eval(normalized_str)
            # If ast.literal_eval results in a list, tuple, dict, recurse
            if isinstance(parsed, (list, dict, tuple)): 
                return normalize_output(parsed)
            elif isinstance(parsed, float) and parsed.is_integer():
                 return int(parsed) 
            return parsed 
        except (ValueError, SyntaxError, TypeError):
            # Attempt 2: If ast.literal_eval fails, check if it's a space-separated list of numbers
            # This is common for competitive programming outputs like "0 1" or "10 20 30"
            parts = normalized_str.split()
            if len(parts) > 1 and all(part.lstrip('-').isdigit() for part in parts): # Check if all parts are integers
                try:
                    return [int(p) for p in parts]
                except ValueError:
                    # Not all parts were valid integers, fall through
                    pass
            elif len(parts) == 1 and parts[0].lstrip('-').isdigit(): # Single number string
                 try:
                    return int(parts[0])
                 except ValueError:
                    pass
            # If all else fails, return the stripped string
            return normalized_str
    
    if isinstance(output, list):
        return [normalize_output(x) for x in output] # Recursively normalize list elements
    
    if isinstance(output, tuple): 
        return [normalize_output(x) for x in list(output)]

    if isinstance(output, dict):
        return {k: normalize_output(v) for k, v in output.items()}

    if isinstance(output, float) and output.is_integer():
        return int(output) 
    
    return output # For types like int, bool, or already processed lists/dicts

# ... (compare_outputs remains the same, relying on the improved normalize_output) ...
def compare_outputs(actual: Any, expected: Any) -> bool:
    try:
        norm_actual = normalize_output(actual)
        norm_expected = normalize_output(expected)
        
        logger.info(f"Comparing outputs:")
        logger.info(f"  Actual (raw): {repr(actual)}, (normalized): {repr(norm_actual)} type: {type(norm_actual)}")
        logger.info(f"  Expected (raw): {repr(expected)}, (normalized): {repr(norm_expected)} type: {type(norm_expected)}")
        
        comparison_result = (norm_actual == norm_expected)
        
        if not comparison_result:
            # This fallback might be less useful now if normalization is robust
            str_norm_actual = str(norm_actual)
            str_norm_expected = str(norm_expected)
            if str_norm_actual == str_norm_expected:
                logger.info("Outputs matched after converting normalized values to strings.")
                return True
            logger.warning(f"Output mismatch: Normalized Actual '{str_norm_actual}' ({type(norm_actual)}) != Normalized Expected '{str_norm_expected}' ({type(norm_expected)})")
        else:
            logger.info(f"Output comparison result: {comparison_result}")

        return comparison_result
        
    except Exception as e:
        logger.error(f"Error comparing outputs: {str(e)}", exc_info=True)
        logger.error(f"Actual: {repr(actual)}, Expected: {repr(expected)}")
        return False