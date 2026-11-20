"""Tiny s-expression reader/writer for KiCad files."""
import re

TOK = re.compile(r'\(|\)|"(?:\\.|[^"\\])*"|[^\s()]+')
BS = chr(92)  # backslash


class Sym(str):
    """Bare (unquoted) atom."""


def parse(text):
    stack = [[]]
    for m in TOK.finditer(text):
        t = m.group(0)
        if t == '(':
            stack.append([])
        elif t == ')':
            v = stack.pop()
            stack[-1].append(v)
        elif t.startswith('"'):
            stack[-1].append(t[1:-1].replace(BS + '"', '"').replace(BS + BS, BS))
        else:
            stack[-1].append(Sym(t))
    return stack[0][0]


def dump(x, ind=0):
    if isinstance(x, list):
        if not x:
            return '()'
        if all(not isinstance(e, list) for e in x):
            return '(' + ' '.join(atom(e) for e in x) + ')'
        out = '(' + atom(x[0])
        for e in x[1:]:
            if isinstance(e, list):
                out += '\n' + '\t' * (ind + 1) + dump(e, ind + 1)
            else:
                out += ' ' + atom(e)
        return out + '\n' + '\t' * ind + ')'
    return atom(x)


def atom(e):
    if isinstance(e, Sym):
        return str(e)
    if isinstance(e, bool):
        return 'yes' if e else 'no'
    if isinstance(e, (int, float)):
        return fmt(e)
    s = str(e).replace(BS, BS + BS).replace('"', BS + '"').replace('\n', BS + 'n')
    return '"' + s + '"'


def fmt(v):
    v = round(float(v), 4)
    if v == int(v):
        return str(int(v))
    return ('%.4f' % v).rstrip('0').rstrip('.')


def find(node, key):
    return [e for e in node if isinstance(e, list) and e and e[0] == key]


def first(node, key):
    r = find(node, key)
    return r[0] if r else None
