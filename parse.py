import json
import re
import html
from bs4 import BeautifulSoup
import unidecode

def strip_links(text):
    pattern = r'\[\[.*\|([^]]+)\]\]'
    replacement = r'\1'
    text = re.sub(pattern, replacement, text)

    pattern = r'\[https?\S* ([^]]+)\]'
    text = re.sub(pattern, replacement, text)
    return text

def strip_html(text):
    bs = BeautifulSoup(text, 'html.parser')
    return bs.get_text()

def remove_categories(text):
    pattern = r'\[\[Category:.*?\]\]'
    cleaned_text = re.sub(pattern, '', text)
    return cleaned_text

def clean_task(task):
    task = strip_links(task)
    task = strip_html(task).lstrip()
    task = unidecode.unidecode(task).lstrip()
    if len(task) == 0:
        return ''

    task = remove_categories(task).lstrip()

    if task.startswith('right\n\n'):
        task = task[7:].lstrip()
        
    if task.startswith(';'):
        task = task[1:]
    if task.startswith('Task:') or task.startswith('task:'):
        task = task[5:].lstrip()


    return task

def extract_syntaxhighlight(input_string):
    start_tag = "<syntaxhighlight"
    end_tag = "</syntaxhighlight>"
    start_tag_len = len(start_tag)
    end_tag_len = len(end_tag)

    max_contents = ""
    stack = []

    i = 0
    while i < len(input_string):
        if input_string[i:i + start_tag_len] == start_tag:
            start_tag_end = input_string.find('>', i)+1
            stack.append(start_tag_end)
            i = start_tag_end
        elif input_string[i:i + end_tag_len] == end_tag:
            if stack:
                start_index = stack.pop()
                contents = input_string[start_index:i]
                if len(contents) > len(max_contents):
                    max_contents = contents
            i += end_tag_len
        else:
            i += 1

    return max_contents

def clean_solution(text):
    longest_code = extract_syntaxhighlight(text)
    longest_code = longest_code if longest_code != '' else text
    longest_code = longest_code.replace('<pre>','').replace('</pre>','')
    return longest_code.lstrip()


min_solution_len = 60
lang_whitelist = ['Python','C','C++','JavaScript']

def language_lookup(language):
    if language in lang_whitelist:
        return language
    for lang in lang_whitelist:
        if language.startswith(lang) and lang != 'C':
            return lang
    return None

def parse_rosettacode(content):
    task = ''
    state = 0
    sections={}
    header_lang=None

    for line in content:
        if '{{clarify task}}' in line or '{{task}}' in line or '{{Task}}' in line or '{{task heading' in line:
            state = 1
            task = line[line.find('}}')+2:]
        elif '{{header' in line:
            language = line[11:line.find('}}')]
            header_lang = language
            if language_lookup(language) is not None:
                state = 2
                sections[language] = ''
            else:
                state = 0
        elif line.startswith('{{Out') or line.startswith('{{out') or line.startswith('{{ out') or line.startswith('{{in') or line.startswith('{{In'):
            state = 0
        elif '{{works with' in line or '{{Works with' in line:
            #print(state, line)
            works_with = line[line.find('{{')+2:line.find('}}')].split('|')
            if len(works_with) < 2:
                print('WARNING: unrecognized works_with', line)
            else:
                language = works_with[1]+' '+works_with[2] if len(works_with) == 3 else works_with[1]
                if language_lookup(language) is not None:
                    state = 2
                    sections[language] = ''
                else:
                    state = 0
        elif line.startswith('{{trans') or line.startswith('{{Trans'):
            trans = line[line.find('{{')+2:line.find('}}')].split('|')
            language = header_lang+' from '+trans[1]
            if language_lookup(language) is not None:
                sections[language] = ''
                state = 2
            else:
                state = 0
        elif line.startswith('{{libheader'):
            state = 0
        elif line.lower().startswith('{{omit from') or line.startswith('{{incorrect') or line.startswith('{{wont work with') or line.startswith('{{Template:'):
            # skip these lines.
            pass
        elif state == 1:
            if line.startswith('{{'):
                print('WARNING: Unrecognized task template', line)
            task += line+'\n'
        elif state == 2:
            if line.startswith('{{'):
                print('WARNING: Unrecognized solution template', line)            
            sections[language] += line+'\n'
        elif state == 3:
            print(line)
            #pass

    output = {'task': clean_task(task), 'solutions': {} }
    for language in sections.keys():
        solution = clean_solution(sections[language])
        if solution == '' or len(solution) < min_solution_len:
            if solution != '':
              print('WARNING: Solution too short:', solution.strip())
            continue
        output['solutions'][language] = solution
    return output

INFILE = 'rosettacode-2023-06-17.jsonl'
OUTFILE = 'solutions-{language}-2023-06-17.jsonl'

total = 0
skip = 0
done = 0
failed = 0
rows = 0

of = {}
for lang in lang_whitelist:
    of[lang] = {
        'fh': open(OUTFILE.format(language=lang), 'w'),
        'langs': [],
        'problems': [],
        'rows': 0
    }

with open(INFILE) as f:
    line = f.readline()
    while line:
        total += 1
        data = json.loads(line)

        if not ('{{task}}' in data['content'] or '{{Task}}' in data['content']):
            skip += 1
        else:
            parsed = parse_rosettacode(data['content'].split('\n'))

            if parsed['task'] == '':
                print('WARNING: Failed to parse task', data['title'])
                failed += 1
            else:

                for language in parsed['solutions'].keys():
                    entry = of[language_lookup(language)]
                    entry['langs'].append(language)
                    if not data['title'] in entry['problems']:
                        entry['problems'].append(data['title'])

                    row = {
                        'title': data['title'],
                        'language': language,
                        'task': parsed['task'],
                        'solution': parsed['solutions'][language]
                    }
                    entry['fh'].write(json.dumps(row)+'\n')
                    rows += 1
                    entry['rows'] += 1
                
                done += 1

        line = f.readline()
        if total % 100 == 0:
            print('Total',total,'done',done,'skip',skip,'failed',failed)

for lang in of.keys():
    of[lang]['fh'].close()
    print('Language', lang, 'problems', len(of[lang]['problems']), 'rows', of[lang]['rows'])

print('Total',total,'done',done,'skip',skip,'failed',failed,'rows',rows)
