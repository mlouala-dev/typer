import torch
from transformers import AutoModelForTokenClassification, AutoTokenizer
from transformers import pipeline
from hadith_ner_helper import split_sentences
import sqlite3

# Load the model
device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
tokenizer = AutoTokenizer.from_pretrained("hatmimoha/arabic-ner")
model = AutoModelForTokenClassification.from_pretrained("hatmimoha/arabic-ner")

nlp = pipeline("ner", model=model, tokenizer=tokenizer)


book = 'mishkat'
source = sqlite3.connect(fr"D:\Script\_rsc\ilm\{book}\{book}.786")
cursor = source.cursor()

dest = sqlite3.connect('./hadith_new.db')
d_cursor = dest.cursor()


class Entity:
    def __init__(self, idx=0, name='', domain=0):
        self.id = idx
        self.name = name
        self.domain = domain

        self.need_to_change = False

    def __eq__(self, other):
        return self.name == other.name


entities = [Entity(i, n, d) for i, n, d in d_cursor.execute('SELECT * FROM entities')]
print('PRELOADED', len(entities))


def add_entity(entity: Entity):
    if len(entity.name):
        if entity not in entities:
            entities.append(entity)
        else:
            list_entity = entities[entities.index(entity)]

            if list_entity.domain != entity.domain:
                if list_entity.need_to_change:
                    list_entity.domain = entity.domain
                    list_entity.need_to_change = False
                else:
                    list_entity.need_to_change = True

        entity.id = entities.index(entity)

        return entity.id


domains_eq = {
  'B-PERSON': 0,
  'B-ORGANIZATION': 0,
  'B-LOCATION': 1,
  'B-DATE': 2,
  'B-PRODUCT': -1,
  'B-COMPETITION': 2,
  'B-EVENT': 2,
  'B-PRIZE': -1,
  'B-DISEASE': -1
}

# Tag the text
try:
    d_cursor.execute('INSERT INTO books (name) VALUES (?)', (book, ))
    dest.commit()
except sqlite3.IntegrityError:
    pass
book_id = d_cursor.execute('SELECT id FROM books WHERE name=?', (book,)).fetchone()[0]

hadiths = cursor.execute('SELECT id, hadith, grade FROM bm_ahadith').fetchall()

for idx, text, grade in hadiths:
    sentences = split_sentences(text)
    try:
        annotations = nlp(sentences)
    except RuntimeError:
        continue

    tokens = []
    for sentence in annotations:
        tokens.extend(sentence)

    tags = []
    for i in range(len(tokens) - 1, 0, -1):
        if tokens[i]['word'].startswith('##'):
            tokens[i - 1]['word'] += tokens[i]['word'].replace('##', '')
            tokens.pop(i)

    hadith_entities = set()
    current_entity = Entity()

    for token in tokens:
        if token['word'] in ('ﷺ', 'ﷻ'):
            continue

        if token['entity'].startswith('B-'):
            hadith_entities.add(add_entity(current_entity))

            current_entity = Entity(name=token['word'], domain=domains_eq[token['entity']])

        elif token['entity'].startswith('I-'):
            current_entity.name += f' {token["word"].strip()}'

    hadith_entities.add(add_entity(current_entity))
    if None in hadith_entities:
        hadith_entities.remove(None)

    print(f'hadith {idx} : ', hadith_entities)
    d_cursor.execute('INSERT INTO hadiths (book_id, book, hadith, grade, entities) VALUES (?, ?, ?, ?, ?)',
                 (idx, book_id, text, grade, ';'.join(map(str, hadith_entities))))

d_cursor.executemany('INSERT OR REPLACE INTO entities (id, name, type) VALUES (?, ?, ?)',
                 [(e.id, e.name, e.domain) for e in entities])

dest.commit()
