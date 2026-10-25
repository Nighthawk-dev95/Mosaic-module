import yaml
import re
import sys

def flatten_strings(obj):
    if isinstance(obj, dict):
        return {k: flatten_strings(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [flatten_strings(v) for v in obj]
    if isinstance(obj, str):
        # collapse all whitespace runs (including newlines) to single spaces
        flat = re.sub(r'\s+', ' ', obj).strip()
        return flat
    return obj

def convert(infile_yaml_body, outfile_yaml_body):
    with open(infile_yaml_body) as f:
        data = yaml.safe_load(f)
    data = flatten_strings(data)
    out = yaml.dump(data, default_flow_style=True, sort_keys=False, width=100000, allow_unicode=True)
    with open(outfile_yaml_body, 'w', newline='\n') as f:
        f.write(out)
    # sanity re-parse
    with open(outfile_yaml_body) as f:
        reparsed = yaml.safe_load(f)
    print(infile_yaml_body, '-> OK. dims:', len(reparsed.get('dimensions', [])), 'measures:', len(reparsed.get('measures', [])), 'joins:', len(reparsed.get('joins', [])))

if __name__ == '__main__':
    convert(sys.argv[1], sys.argv[2])
