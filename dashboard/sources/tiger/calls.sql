select session_id, tool_call_id, position, turn, tool_name, command_class, test_runner,
       duration_s::float8 as duration_s, is_error, output_tokens_est
from primitives_calls
