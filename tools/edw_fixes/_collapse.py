import re

def collapse_backslash_continuations(text):
    lines = text.split('\n')
    out = []
    i = 0
    while i < len(lines):
        line = lines[i]
        rstripped = line.rstrip()
        if rstripped.endswith('\\') and not rstripped.endswith('\\\\'):
            buf = rstripped[:-1]
            i += 1
            while i < len(lines):
                cont = lines[i]
                stripped = cont.lstrip()
                cont_rstripped = stripped.rstrip()
                ends_cont = cont_rstripped.endswith('\\') and not cont_rstripped.endswith('\\\\')
                if stripped.startswith('\\ '):
                    piece = ' ' + stripped[2:]
                elif stripped.startswith('\\'):
                    piece = stripped[1:]
                else:
                    piece = stripped
                if ends_cont:
                    piece_core = piece.rstrip()[:-1]
                    buf += piece_core
                    i += 1
                    continue
                else:
                    buf += piece
                    out.append(buf)
                    i += 1
                    break
            else:
                out.append(buf)
        else:
            out.append(line)
            i += 1
    return '\n'.join(out)

for fname in ['015a_test_mosaic_volume_metric_view.sql', '015b_test_mosaic_resident_utilization_metric_view.sql']:
    with open(fname, 'r', newline='\n') as f:
        content = f.read()
    new_content = collapse_backslash_continuations(content)
    outname = fname.replace('.sql', '_flat.sql')
    with open(outname, 'w', newline='\n') as f:
        f.write(new_content)
    print(fname, '->', outname, 'lines before/after:', content.count('\n'), new_content.count('\n'))
