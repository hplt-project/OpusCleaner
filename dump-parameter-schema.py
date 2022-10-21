#!/usr/bin/env python3
import sys
import argparse
import json
from typing import Union, Literal, Any, cast, Dict

script_path = sys.argv[1]

# Remove the script name from the argument list
sys.argv[1:] = sys.argv[2:]


def _argparse_parse_args(self: argparse.ArgumentParser, args=None, namespace=None):
	"""Creates a json string from the argparser instance"""
	json_out: Dict[str,Any] = {}
	json_out["type"] = "bilingual/monolingual" #TODO "monolingual" or "bilingual" but no idea how to determine this automatically
	json_out["description"] = self.description

	# non-simple type so it doesn't end up in json
	SWITCH = object()
	SUBSTITUTE = object()

	# We need to skip [0], as this is the prepended `--help`
	param_dict: Dict[str,Dict] = {}
	for argument in self._actions[1:]:
		# Skip --help and --version
		if isinstance(argument, (argparse._HelpAction, argparse._VersionAction)):
			continue

		current_str = {
			"help": argument.help,
			"required": argument.required
		}

		if isinstance(argument, argparse._StoreConstAction):
			current_str |= {
				"type": "bool",
				"default": False
			}
		elif type(argument.type) == type:
			current_str |= {
				"type": cast(type, argument.type).__name__,
				"default": argument.default
			}
		elif type(argument.type) == argparse.FileType:
			current_str |= {
				"type": "str",
				"default": "-"
			}
		elif argument.default is not None:
			current_str|= {
				"type": type(argument.default).__name__,
				"default": argument.default
			}
		else:
			print(f"Unknown type for \"{argument.dest}\": skipped\n{argument!r}\n", file=sys.stderr)
			continue
		

		# If it is an `--option` type argument
		if argument.option_strings:
			current_str |= {
				SWITCH: argument.option_strings[0], #TODO prefer long names?
				SUBSTITUTE: argument.option_strings[0].replace('-','').upper()
			}
		# or a positional one
		else:
			current_str |= {
				SUBSTITUTE: argument.dest.upper()
			}

		if argument.choices is not None:
			current_str |= {
				"allowed_values": argument.choices
			}

		# Add to the parameter dict
		param_dict[current_str[SUBSTITUTE]] = current_str

	json_out["parameters"] = param_dict

	json_out["command"] = script_path
	for _, value in param_dict.items():
		if not value["required"]:
			json_out["command"] += " ${" + value[SUBSTITUTE] + ":+" + value[SWITCH] + (" $" + value[SUBSTITUTE] if value["type"] != "bool" else "") + "}"
		else:
			json_out["command"] += (" " + value[SWITCH] if SWITCH in value else "") + " $" + value[SUBSTITUTE]

	json.dump(json_out, sys.stdout, indent=4, skipkeys=True)
	sys.exit(0)


argparse.ArgumentParser.parse_args = _argparse_parse_args

with open(script_path) as fh:
	exec(fh.read())
