import yaml
from dataclasses import dataclass
import re
import argparse

placeholders, placeholder_cnt = [], 0

parser = argparse.ArgumentParser()
parser.add_argument('-c', '--config', type=str, help='Path to yaml configuration file', required=True)
parser.add_argument('-s', '--source_file', type=str, help='Path to the input file')
parser.add_argument('-t', '--target_file', type=str, help='Path to the target file', required=True)
mutex_group_1 = parser.add_mutually_exclusive_group(required=True)
mutex_group_1.add_argument('--decode', action='store_true')
mutex_group_1.add_argument('--encode', action='store_true')

@dataclass
class Rule(object):
    pattern: str

class Text(str):

    def make_placeholders(self, *rules: list[Rule]):
        global placeholder_cnt, placeholders
        for rule in rules:
            for grp in [match.group() for match in re.finditer(rule.pattern, self)]:
                if grp not in placeholders:
                    placeholders.append(grp)
                    number_to_insert = placeholder_cnt
                    placeholder_cnt += 1
                else:
                    number_to_insert = placeholders.index(grp)
                self = re.sub(grp, f'@{number_to_insert}', self)
                
        return self

    def replace_placeholders(self, placeholders: list[str]):
        for i, placeholder in enumerate(placeholders):
            self = re.sub(f'@{i}', placeholder, self)
        return self

def get_src() -> str:
    if not args.source_file:
        return [input()]
    with open(args.source_file, 'r') as f:
        text = f.readlines()
    return text

def encode() -> None:
    with open(args.target_file, 'w') as target_file, \
         open(args.config, 'r') as config_file:
        config, text = yaml.safe_load(config_file), get_src()
        rules = [Rule(regex) for regex in config['regexes']]
        [target_file.write(Text(line).make_placeholders(*rules)) for line in text]
        # target_file.write(Text(text).make_placeholders(*rules))
        config["placeholders"] = placeholders
    with open(args.config, 'w') as config_file:  
        yaml.dump(config, config_file, allow_unicode=True)

def decode() -> None:
    with open(args.config, 'r') as config_file, \
         open(args.target_file, 'w') as target_file:
        text = get_src()
        placeholders = yaml.safe_load(config_file)['placeholders']
        [target_file.write(Text(line).replace_placeholders(placeholders)) for line in text]
        # target_file.write(Text(text).replace_placeholders(placeholders))
        
if __name__ == "__main__":
    args = parser.parse_args()
    encode() if args.encode else decode()
