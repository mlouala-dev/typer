import sqlite3
import os


def appdata_path(file: str = '') -> str:
    """
    returns absolute path to the %appdata%/Local/Typer
    """
    return os.path.join(os.getenv('LOCALAPPDATA'), 'Typer', file)


con = sqlite3.connect(appdata_path('corpus.db'))
cur = con.cursor()


def update(sid, did, sw, dw, word):
    print(f'REALIGN {sid} TO {did}')
    cur.execute(
        'UPDATE dict SET weight=? WHERE id=?',
        (sw + dw, did)
    )
    cur.execute(
        'UPDATE dict SET lemma=? WHERE lemma=?',
        (did, sid)
    )
    cur.execute(
        'UPDATE dict SET lemma=? WHERE lemma=?',
        (did, word)
    )
    cur.execute(
        'DELETE FROM dict WHERE id=?',
        (sid,)
    )
    for field in ('x1', 'x2', 'word_id'):
        try:
            cur.execute(
                f'UPDATE predikt SET {field}=? WHERE {field}=?',
                (did, sid)
            )
        except sqlite3.IntegrityError:
            psw = cur.execute(f'SELECT w FROM predikt WHERE {field}=?', (sid,)).fetchone()[0]
            pdw = cur.execute(f'SELECT w FROM predikt WHERE {field}=?', (did,)).fetchone()[0]
            cur.execute(
                f'UPDATE predikt SET w=? WHERE {field}=?',
                (psw + pdw, did)
            )
            cur.execute(
                f'DELETE FROM predikt WHERE {field}=?',
                (sid,)
            )


def TRANSLATE(SRC, DST):
    consumed = 0

    source_res = cur.execute('SELECT * FROM dict WHERE word=? ORDER BY weight DESC', (SRC,)).fetchall()
    dest_res = cur.execute('SELECT * FROM dict WHERE word=? ORDER BY weight DESC', (DST,)).fetchall()

    for sid, sword, srole, slemma, sw in source_res:
        for did, dword, drole, dlemma, dw in dest_res:
            if srole == drole:
                update(sid, did, sw, dw, sword)
                consumed += 1

    print(consumed, len(source_res))

    if consumed == 0 and len(source_res) == 1 and len(dest_res):
        best = dest_res[0]
        update(source_res[0][0], best[0], source_res[0][-1], best[-1], source_res[0][1])

    con.commit()


def DELETE(SRC):
    consumed = 0

    targets = cur.execute('SELECT * FROM dict WHERE word=? ORDER BY weight DESC', (SRC,)).fetchall()

    for sid, sword, srole, slemma, sw in targets:
        cur.execute('DELETE FROM dict WHERE id=?', (sid,))

        for field in ('x1', 'x2', 'word_id'):
            cur.execute(f'DELETE FROM predikt WHERE {field}=?', (sid, ))

        cur.execute(
            'UPDATE dict SET lemma=? WHERE lemma=?',
            (sword, sid)
        )

        consumed += 1

    print(consumed, len(targets))
    con.commit()


TRANSLATE('muhammed', "Muhammad")
# DELETE('hadithsqui')

