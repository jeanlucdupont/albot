#!/usr/bin/env python3
"""Extract candidate IPs, URLs, domains and hashes from UTF-8 text. Python 3.9+."""
import argparse
import csv
import ipaddress
import json
from pathlib import Path
import re
import sys
from urllib.parse import urlsplit

VERSION = '1.0.0'
URL = re.compile(r'\b(?:https?|hxxps?)\s*(?::|\[:\])//[^\s<>"\x27]+', re.I)
HASH = re.compile(r'(?<![a-zA-Z0-9_])(?:[a-fA-F0-9]{64}|[a-fA-F0-9]{40}|[a-fA-F0-9]{32})(?![a-zA-Z0-9_])')
# Conservative ASCII DNS names, including common dot-defanging forms.
DOT = r'(?:\.|\[\.\]|\(\.\)|\{\.\})'
LABEL = r'[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?'
DOMAIN = re.compile(r'(?<![a-zA-Z0-9_.-])(?:'+LABEL+DOT+r')+[a-zA-Z]{2,63}(?![a-zA-Z0-9_-])')
IPV4 = re.compile(r'(?<![a-zA-Z0-9_.])(?:\d{1,3}'+DOT+r'){3}\d{1,3}(?![a-zA-Z0-9_.])')
IPV6 = re.compile(r'(?<![a-zA-Z0-9_:])(?:[a-fA-F0-9]*:){2,}[a-fA-F0-9:.]*(?:%[a-zA-Z0-9_-]+)?(?![a-zA-Z0-9_:])')


def refang(value):
    value = re.sub(r'\[\.\]|\(\.\)|\{\.\}', '.', value)
    value = re.sub(r'^hxxp', 'http', value, flags=re.I)
    return re.sub(r'\s*(?::|\[:\])//', '://', value, count=1)


def trim_url(value):
    value = value.rstrip('.,;!?')
    for opening, closing in [('(', ')'), ('[', ']'), ('{', '}')]:
        while value.endswith(closing) and value.count(closing) > value.count(opening):
            value = value[:-1]
    return value


def extract_line(line):
    found = []
    for match in URL.finditer(line):
        raw = trim_url(match.group())
        value = refang(raw)
        try:
            parsed = urlsplit(value)
            host = parsed.hostname
            if not host or parsed.scheme.lower() not in ('http', 'https'):
                continue
            parsed.port  # Reject malformed ports.
            value = parsed.scheme.lower() + value[len(parsed.scheme):]
            found.append(('url', value, match.start(), match.start()+len(raw), raw))
        except ValueError:
            continue
    for match in HASH.finditer(line):
        value = match.group().lower()
        found.append(({32:'md5',40:'sha1',64:'sha256'}[len(value)], value, match.start(), match.end(), match.group()))
    for pattern in (IPV4, IPV6):
        for match in pattern.finditer(line):
            try:
                value = str(ipaddress.ip_address(refang(match.group())))
            except ValueError:
                continue
            found.append(('ipv6' if ':' in value else 'ipv4', value, match.start(), match.end(), match.group()))
    for match in DOMAIN.finditer(line):
        value = refang(match.group()).lower()
        if len(value) <= 253:
            found.append(('domain', value, match.start(), match.end(), match.group()))
    # Domains/IPs inside URLs are intentionally separate searchable indicators.
    return sorted(set(found), key=lambda row:(row[2],row[0],row[1]))


def collect(paths, encoding, context):
    indicators = {}
    for path in paths:
        with path.open(encoding=encoding) as stream:
            for number, line in enumerate(stream, 1):
                for kind, value, start, end, raw in extract_line(line):
                    key = (kind, value)
                    item = indicators.setdefault(key, {'type':kind,'value':value,'occurrences':[]})
                    occurrence = {'source_file':str(path.resolve()), 'line':number,
                                  'column':start+1, 'raw':raw}
                    if context:
                        occurrence['context'] = line.rstrip('\r\n')
                    item['occurrences'].append(occurrence)
    return sorted(indicators.values(),key=lambda x:(x['type'],x['value']))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('files', nargs='+', type=Path, help='Text files to scan')
    parser.add_argument('--format',choices=('json','csv'),default='json')
    parser.add_argument('--output',type=Path,help='New output file; otherwise write to stdout')
    parser.add_argument('--encoding',default='utf-8-sig',help='Input encoding, default utf-8-sig')
    parser.add_argument('--context',action='store_true',help='Include full source lines')
    parser.add_argument('--version',action='version',version=VERSION)
    args = parser.parse_args(argv)
    try:
        # Repeated filenames must not double-count occurrences.
        paths = list(dict.fromkeys(p.resolve(strict=True) for p in args.files))
        if any(not p.is_file() for p in paths):
            raise ValueError('Inputs must be regular text files')
        rows = collect(paths,args.encoding,args.context)
        stream = args.output.open('x',encoding='utf-8',newline='') if args.output else sys.stdout
        try:
            if args.format == 'json':
                json.dump(rows,stream,ensure_ascii=False,indent=2)
                stream.write('\n')
            else:
                writer=csv.writer(stream)
                writer.writerow(['type','value','occurrence_count','occurrences_json'])
                for row in rows:
                    # Prevent spreadsheet execution of a URL containing a formula-like prefix.
                    value=row['value']
                    if value.lstrip().startswith(('=','+','-','@')) or value.startswith(("'",'\t','\r','\n')):
                        value="'"+value
                    writer.writerow([row['type'],value,len(row['occurrences']),json.dumps(row['occurrences'],ensure_ascii=False)])
        finally:
            if args.output:
                stream.close()
        print(f'{len(rows)} unique candidate indicators',file=sys.stderr)
        return 0
    except (OSError,ValueError,LookupError) as exc:
        print(f'Error: {exc}',file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
