# بسم الله الرحمان الرحيم
"""
This lib converts a latin translitteration to arabic
TODO: multiple translitteration settings, even user defined ?
TODO: trim space after "wa"
"""
import re
from tools.G import appdata_path


class Letter:
    """
    A simple class to handle the arabic letters, by letter with harakat
    """
    def __init__(self, parent: list, index=-1, letter='', accent=''):
        self.parent = parent
        self.letter = letter
        self.accent = accent

        if index == -1:
            self.id = len(self.parent)

    @property
    def previous(self):
        """
        returns the previous letter
        :rtype Letter
        """
        return self.parent[max(0, self.id - 1)]

    @property
    def next(self):
        """
        returns the next letter
        :rtype Letter
        """
        return self.parent[min(self.id + 1, len(self.parent) - 1)]

    def __eq__(self, other):
        """
        :type other: Letter | tuple
        """
        if isinstance(other, Letter):
            return self.letter == other.letter and self.accent == other.accent
        return self.letter == other[0] and self.accent == other[1]

    def __repr__(self):
        return f'{self.letter}[{self.accent}]'


L = Letter([], letter='l')
Alif = Letter([], letter="'")
Li = Letter([], letter='l', accent='i')
La = Letter([], letter='l', accent='a')
Aa = Letter([], letter="'", accent='aa')


# the arabic letters equivalence
hurufs = frozenset(('kh', 'th', 'dh', 'gh', 'sh', 'z', 'r', 't', 'T', 'Z',
                    'q', 's', 'S', 'D', 'd', 'f', 'j', 'h', 'H', 'k', 'x',
                    'l', 'm', 'w', 'b', 'n', 'y', "''", '"', "'", " "))

# all arabic letters
arabic_hurufs = frozenset('ذضصثقفغعهخحجدشسيبلاتنمكطئءؤرىةوزظإأـ')
arabic_digits = list("٠١٢٣٤٥٦٧٨٩")

# translitteration matching, accept duplicates
matching = {
    'kh': "خ", 'th': "ث", 'dh': "ذ", 'gh': "غ", 'sh': "ش", 'z': "ز", 'r': "ر", 't': "ت", 'T': "ط", 'Z': "ظ", 'k': "ك",
    'q': "ق", 's': "س", 'S': "ص", 'D': "ض", 'd': "د", 'f': "ف", 'j': "ج", 'h': "ه", 'H': "ح", 'l': "ل", 'm': "م",
    'w': "و", 'b': "ب", 'n': "ن", 'y': "ي", "''": "ع", '"': "ع", "'": "ا", "": "ا", " ": " ", "x": "ة"
}

# for sheddah after alif lam
huruf_shamsya = frozenset(["z", "r", "t", "s", "sh", "n", "d", "dh"])

# how we mark a tashkil on a letter
harakaat = {
    "aa": "َ",
    "a": "َ",
    "ii": "ِي",
    "i": "ِ",
    "uu": "ُو",
    "u": "ُ",
    "": ""
}


re_clean_al = re.compile(r"^ال")
re_clean_harakat = re.compile(r"[ًٌٍَُِ~ّ]")
re_ignore_hamza = re.compile(r'[أإآ]')

# we try to get out dictionary containing all words with a madd at the end and wrote with ى
try:
    with open(appdata_path('dict_alif_maqsuur.txt'), mode="r", encoding="utf-8") as my_file:
        ar_words = my_file.readlines()

except FileNotFoundError:
    ar_words = []

# remove trailing return char
finally:
    ar_dict = [a.replace("\n", "")[:-1] for a in ar_words]


def clean_harakat(text: str) -> str:
    return re_clean_harakat.sub('', text)


def explode_arabic(text: str) -> [Letter]:
    """
    Will convert a text variable to a list of tuples (letter, tashkil) :
    for instance "qaal" will become ('q', 'aa'), ('l', '')
    :param text: the translitterated string
    :return: a list of Letter
    """
    letters = list()

    pos = 0     # the cursor's position
    wlen = 0    # this is the word length

    # looping through each letters
    while pos < len(text):
        delta = 1

        # if we find a letter like 'dh' or 'kh'
        if text[pos:pos + 2] in hurufs:

            # storing the letter first
            letters.append(Letter(parent=letters, letter=text[pos:pos + 2]))
            delta = 2
            wlen += 2

        # if we find a letter like 'q' or 'b'
        elif text[pos:pos + 1] in hurufs:
            letters.append(Letter(parent=letters, letter=text[pos:pos + 1]))
            wlen += 1

        # if there is no previous match, we make sure there is no match in lower case,
        # if ever the used mistyped
        elif text[pos:pos + 1].lower() in hurufs:
            letters.append(Letter(parent=letters, letter=text[pos:pos + 1].lower()))
            wlen += 1

        # now we check for an isolated tashkil like in 'albayt' or 'uSuul'
        elif wlen == 0 and text[pos:pos + 1] in 'aiu':

            # if no letter mentioned, it means it's a hamza
            letters.append(Letter(parent=letters, letter="'", accent=text[pos:pos + 1]))

        # finally if none of the above options worked, it means we met a harakat
        else:
            letters[-1].accent += text[pos:pos + 1]

        # we don't count it as a char if this is a space
        if letters[-1].letter == " ":
            wlen = 0

        # if word is longer than two char (it won't match 'huwa' or 'hiya')
        # we automatically add a ة at the end like in 'faaTima'
        if wlen > 2 and letters[-1].letter == "a" and pos == (len(text) - 1):
            letters.append(Letter(parent=letters, letter="x", accent=""))

        # moving the cursor
        pos += delta

    return letters


def get_arabic_numbers(val: str, arabic=False) -> str:
    """
    this function converts every digit into its 'arabic' - actually hindi digits
    :param val: the numeric value to convert
    :param arabic: if we want to force RTL on the returned text because 'val' is wrote in arabic
    :return: a string with arabic digits
    """
    val = str(val)

    # inserting the force RTL character if arabic var
    force_arabic = "&#x200e;" if arabic else ""
    arabic_cmd = ""

    # trying to convert every character
    for character in val:
        try:
            arabic_cmd += arabic_digits[int(character)]

        # if we can't find it, adding the original char
        except ValueError:
            arabic_cmd += force_arabic + character

    return arabic_cmd


def append_to_dict(word: str):
    """
    we update the current dict of ى with a new one
    :param word: the new word to add
    """
    # also altering the ar_dict used by the next function to get live update
    global ar_dict

    try:
        # cleaning the word before storing
        word = clean_harakat(word)

        # we first make sure our word is not in ar_dict
        assert word.endswith("ى") and word[:-1] not in ar_dict

        # now we can update the dict
        with open(appdata_path('dict_alif_maqsuur.txt'), 'a', encoding='utf-8') as f:
            f.write(f'{word}\n')

        ar_dict.append(word[:-1])

    # if the word doesn't meet requirements
    except AssertionError:
        pass


def translitterate(text: str, no_harakat=False) -> str:
    """
    This main function converts a latin transliterration string to arabic
    TODO: load different transliterration rules

    :param text: the text to convert
    :param no_harakat: do not return the arabic's text with arabic TODO: embed in settings
    :return: the converted arabic string
    """
    # if the text is arabic, returning as it, just apply the no_harakat if needed
    if text[0] in arabic_hurufs:
        return clean_harakat(text) if no_harakat else text

    # first getting our list of (characters, tashkil)
    letters = explode_arabic(text)

    final = ''
    char_cnt, char_last = 0, False

    def get_previous_word(word):
        """
        checks if the given word is in global dict ar_dict and ends with a ى
        :param word: the word to check
        :return: an updated word if it has ى instead of ا
        """
        # pre-cleaning
        previous_word = clean_harakat(word.split(" ")[-1])

        # if it ends with a ا we check he's in dict
        if previous_word.endswith('ا'):
            try:
                assert previous_word[:-1] in ar_dict
                # if it's not in the dict we replace its last char with a ى
                return word[:-2] + "ى"

            except AssertionError:
                pass

        return word

    # looping through all words' characters
    for harf in letters:
        POST: Letter
        PRE: Letter

        i = harf.id
        letter = harf.letter
        accent = harf.accent
        POST = harf.next
        PRE = harf.previous

        # if previous word's done, checking it should end with a ى
        if letter == " ":
            final = get_previous_word(final)
            char_cnt = 0
        else:
            char_cnt += 1

        # this indicates if we're on the last character of a word
        char_last = i < (len(letters) - 1) and POST.letter == ' ' or i == (len(letters) - 1)

        # the alif character can 'wear' different hamza variant depending
        # on it's tashkil but also the previous one
        if letter == "'":
            if accent == "a" and (PRE.accent == '' or PRE.accent == 'a') and char_cnt >= 2 and not char_last:
                final += "أ"
            elif accent == "u" and (i == 0 or (i > 0 and PRE.letter == " ")):
                final += "أ"
            elif char_cnt == 1:
                final += "ا"
                harf.accent = accent = ""
            elif char_last and accent == "a":
                final += "ى"
            elif char_last and accent == "":
                final += "ء"
            elif accent == 'a' and 'a' in PRE.accent:
                final += "ء"
            elif 'i' in accent and not PRE.accent == '' or 'i' in PRE.accent and not PRE.letter == 'b':
                final += "ئ"
            elif 'i' in accent and PRE.accent == '':
                final += "إ"
            elif 'u' in PRE.accent:
                final += "ؤ"
            else:
                final += matching[letter]

        # if it's not an alif we don't need to check which variant of the letter we paste
        else:
            final += matching[letter]

        # if the letter is doubled and the previous didn't have accent like 'zilla'
        if i > 0 and PRE.letter == letter and PRE.accent == '' and len(PRE.accent) < 2:
            final = final[:-1]
            final += "ّ"

        # we add a sheddah when words starts with 'al' and a harf shamsiyya like 'alshams'
        if letter in huruf_shamsya and char_cnt >= 3 and PRE == L and PRE.previous == Alif:
            final += "ّ"

        # if this is not a space, we check its tashkil
        if matching[letter] != " ":
            harakat = ''
            try:
                assert not accent.isupper()
                harakat = harakaat[accent]

            # if the accent is too long (maybe used mistyped)
            except KeyError:
                harakat = harakaat[accent[:2]]

            # if the accent was uppercase
            except AssertionError:
                harakat = harakaat[accent.lower()]

            # now we can add the correct harakat to the word
            finally:
                final += harakat

            # if we have an alif with fatha madd we change the character like "al'aaya"
            if harf == Aa:
                final = final[:-2]
                final += "آ"

            # trying a simple guess based on the root of the word - usually word with a ي in middle
            # will end with a ى when last letter is madd like in
            elif accent == "aa":
                if letter == "y" and char_last:
                    final += "ى"
                else:
                    final += "ا"

        # final tries for some exceptions
        try:
            # if the previous letter was not a space and ending with a 'a' we usually have ة
            if accent == 'a':
                if i >= 1 and PRE.letter != " " and char_last:
                    final += "ة"

            if PRE.previous.previous == Alif and PRE.previous == L and PRE == La and letter == 'h':
                final = final[:-6] if accent != "" else final[:-5]
                final += "الله"

            # special case for 'lillah'
            elif PRE.previous.previous == Li and PRE.previous != L and PRE == La and letter == 'h':
                final = final[:-5] if accent != "" else final[:-4]
                final += "للّه"

            # special case for 'lillah'
            elif PRE.previous.previous == Li and PRE.previous == L and PRE == La and letter == 'h':
                final = final[:-7] if accent != "" else final[:-6]
                final += "لِلّه"

        except IndexError:
            pass

    # we finally check the last word to make sure everybody has been formatted properly
    final = get_previous_word(final)

    return clean_harakat(final) if no_harakat else final


if __name__ == "__main__":
    print(translitterate('''laa ilaah illaa allah'''))
