select session_id, tool_call_id, position, turn, tool_name, command_class, test_runner,
       path_arg_count, duration_s::float8 as duration_s, is_error, exit_code, output_tokens_est
from primitives_calls
