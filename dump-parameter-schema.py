#!/usr/bin/env python3
import sys
import argparse
import json
from typing import Union, Literal, Any, cast

script_path = sys.argv[1]

# Remove the script name from the argument list
sys.argv[1:] = sys.argv[2:]


def _argparse_parse_args(self: argparse.ArgumentParser, args=None, namespace=None):
	"""Creates a json string from the argparser instance"""
	json_out: dict[str,Any] = {}
	json_out["type"] = "bilingual/monolingual" #TODO "monolingual" or "bilingual" but no idea how to determine this automatically
	json_out["description"] = self.description
	
	# non-simple type so it doesn't end up in json
	SWITCH = object() 
	SUBSTITUTE = object()

	# We need to skip [0], as this is the prepended `--help`
	param_dict: dict[str,dict] = {}
	for argument in self._actions[1:]:
		current_str = {
			SWITCH: argument.option_strings[0], #TODO prefer long names?
			SUBSTITUTE: argument.option_strings[0].replace('-','').upper(),
			"type": cast(type, argument.type).__name__ if type(argument.type) == type else "bool",
			"required": argument.required,
			"default": argument.default,
			"help": argument.help
		}

		if argument.choices is not None:
				current_str["allowed_values"] = argument.choices
		
		# Add to the parameter dict
		param_dict[current_str[SUBSTITUTE]] = current_str

	json_out["parameters"] = param_dict

	json_out["command"] = script_path
	for _, value in param_dict.items():
			if value["type"] == "bool":
				json_out["command"] += " ${" + value[SUBSTITUTE] + ":+" + value[SWITCH] + "}"
			else:
				json_out["command"] += " " + value[SWITCH] + " $" + value[SUBSTITUTE]

	json.dump(json_out, sys.stdout, indent=4, skipkeys=True)
	sys.exit(0)


argparse.ArgumentParser.parse_args = _argparse_parse_args

with open(script_path) as fh:
	exec(fh.read())
