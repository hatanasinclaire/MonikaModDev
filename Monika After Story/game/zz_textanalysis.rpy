# Functions for the conversion of dialogue to speech shapes ("visemes").

init -500 python in mas_textanalysis:

    import re
    # import eng_to_ipa as ipa # Needs Python3
    # import inflect # Needs Python3
    # p = inflect.engine()

    def process_text(input_string, input_cps = None):
        """
            This function takes in takes in a text input with Ren'Py timing information and converts it into the information necessary for facial animation.

            The function checks the timing information so that the facial animation will finish at the same time as the text on the screen finishes printing.

            Any given line may vary characters per second (hereon referred to as "cps") within, using Ren'Py's timing tags {cps=}{/cps}, {w=}, and {fast}.
            Therefore, the output is recursively evaulated as "chunks" of constant cps. If, for example, the first part of a line is at default speed and the
            second half uses a {cps} tag to display at half speed, those are two separate chunks. Waits specified with {w=} are also their own chunk. In the
            final output, each viseme is specified with the cps from its chunk.

            Dialogue before a {fast} tag is shown instantly in Ren'Py. Therefore, any text before such a tag will not be converted to visemes.

            Inputs:
                input_string - the string to be converted.
                input_cps - used for recursive purposes, can also manually set the cps of a string with this. Defaults to the cps specified by game settings.
            Outputs:
                list of tuples - each item in the list is a tuple with two elements: the first is the number of the viseme, and the second is a float
                specifying how many seconds that viseme is shown.

            Mechanism:
                The function first uses regex to check for timing tag and to break the dialogue into timing "chunks" recursively.

                The regexed segments are then converted into their English pronunciations using regexed_text_to_phonemes(). Pronunciation in English is often
                represented using the International Phonetic Alphabet (IPA), a standardized system used to describe sounds in human speech. The system uses
                eng-to-ipa's convert() function to convert the text to the IPA representation of how it is pronounced. However, eng-to-ipa cannot produce the
                pronunciation of every word, as there will naturally be unfamiliar words it doesn't recognize. Because letters do not correspond directly to
                sounds in the English language, a secondary function, unknown_words_to_ipa(), is used to manually specify pronunciation for some of the words
                that eng-to-ipa does not recognize, and guess the pronunciation of words not manually specified.

                The IPA pronunciation of the line is converted into the appropriate facial shapes using a phonemes_to_visemes(). Though there are around 40-50
                different sounds ("phonemes") commonly used in English, there are only half as many different facial shapes ("visemes") as some sounds will
                make the same mouth shape. For example, the mouth makes the same shape when pronouncing "cat" and "cut".

                The function then calculates how many seconds are required for each viseme to be displayed, and includes this value in a tuple.
        """

        if input_string == "":
            return []

        # set cps
        if input_cps == None:
            cps = renpy.game.preferences.text_cps
        else:
            cps = input_cps

        regex_line = input_string.lower()

        # remove all text before {wait} tags since that dialogue is displayed instantly
        regex_line = re.sub(".*{fast}", "", regex_line)

        # check to see if there's any text enclosed by {cps=} tags
        cps_check = re.search("{cps=\*?[0-9.]+}(.*?){/cps}", regex_line)
        # if so, process the areas outside of the cps tags recursively
        if cps_check is not None:
            cps_amount = re.search("{cps=\*?[0-9.]+}", cps_check.group(0)).group(0)
            if "*" in cps_amount: # tag uses a cps multiplier
                cps_override = cps * float(re.sub("[^0-9.]+", "", cps_amount))
            else: # tag uses a raw cps value
                cps_override = float(re.sub("[^0-9.]+", "", cps_amount))

            split_regex_line = re.split("{cps=\*?[0-9.]+}(.*?){/cps}", regex_line, maxsplit = 1)
            return process_text(split_regex_line[0], input_cps = cps) + process_text(split_regex_line[1], input_cps=cps_override) + process_text(split_regex_line[2], input_cps = cps)

        # check to see if there's any {w=} tags
        # {w=} tags could occur within text enclosed by {cps=} tags, so this check comes second.
        wait_check = re.search("{w=[0-9\.]+}", regex_line)
        # if so, specify the length of the wait segment and handle the rest recursively
        if wait_check is not None:
            wait_string = wait_check.group(0)
            wait_amount = re.sub("[^0-9.]+", "", wait_string)

            split_regex_line = re.split("{w=[0-9\.\*]+}", regex_line, maxsplit = 1)
            return process_text(split_regex_line[0], input_cps = cps) + [(0, float(wait_amount))] + process_text(split_regex_line[1], input_cps = cps)

        # strip out any remaining tags
        regex_line = re.sub("{[^}]*}", "", regex_line)

        # this is the number of characters that will be displayed in the dialogue box
        number_of_characters = len(regex_line)

        # convert numbers to text using inflect
        # needs python 3
        # !!! CHANGE TO: !!!
        # regex_line = re.sub("[01234567890.]*\d+", lambda nums: p.number_to_words(nums.group(0)), regex_line)

        # convert hyphens to space
        regex_line = re.sub("[-]{1}", " ", regex_line)

        # filter only to a-z '.?!,;:
        regex_line = re.sub("[^a-z\'.?!,;:\s]{1}", "", regex_line)

        # run conversion
        # convert text to pronunciation
        phoneme_list = regexed_text_to_phonemes(regex_line)
        # convert pronunciation
        viseme_list = phonemes_to_visemes(phoneme_list)

        # trim any trailing "0" phonemes. may be unnecessary?
        while len(viseme_list) > 0:
            if viseme_list[-1] == 0:
                viseme_list.pop(-1)
            else:
                break

        # input is not empty but there are no visemes to show (example: "...")
        if len(viseme_list) == 0:
            return []

        number_of_visemes = float(len(viseme_list))
        seconds_per_viseme =  number_of_characters / (number_of_visemes * cps)

        # round timing to closest 1/100ths of a second
        seconds_per_viseme = round(seconds_per_viseme, 2)

        output_list = []
        for viseme in viseme_list:
            output_list.append((viseme, seconds_per_viseme))

        return output_list

    def regexed_text_to_phonemes(input_string):
        """
            It calls eng-to-ipa to figure out the pronunciation of the input text.
            It then uses unknown_words_to_ipa() to try to find any unknown words eng-to-ipa didn't catch.
            However, due to the nature of the English language, there will still be words it can't figure
            out how to pronounce, for which it will do its best to guess the pronunciation.

            Input: string - processed text to be converted.
            Output: string - IPA pronunciation of input text.
        """

        # convert to IPA
        # ipa_line = ipa.convert(input_string)

        # check to see if we have pronunciations for unknown words
        # ipa_line = re.sub("[\S]+\*", lambda unknown_words: unknown_words_to_ipa(unknown_words.group(0)), ipa_line)

        # Reduced version of regexed_text_to_phonemes() functionality as eng-to-ipa requires Py3 / R8 migration

        ipa_line = re.sub("[\S]+", lambda unknown_words: unknown_words_to_ipa(unknown_words.group(0)), input_string)

        return ipa_line


    def phonemes_to_visemes(input_string):
        """
            It converts strings of phonemes in IPA to a list of visemes to describes which sprites to use.
            The function uses lookup tables to convert the string starting from the left.
            It first checks for trigraphs of three characters, then digraphs of two, then for single characters.
            In this way it iterates through the whole input string.

            Input: string - IPA pronunciation of current string.
            Output: list of integers - indicating sequence of visemes (mouth shapes).
        """

        ipa_trigraphs = {
            "aɪɹ": [8,6,2],
            "aʊɹ": [8,1,2]
        }

        ipa_digraphs = {
            "eɪ": [1,6],
            "oʊ": [12,1],
            "aɪ": [8, 6],
            "aʊ": [8,1],
            "ɔɪ": [10,6],
            "ju": [6,11],
            "ɪɹ": [6,2],
            "ɛɹ": [1,2],
            "ʊɹ": [1,2],
            "ɔɹ": [10,2],
            "ɑɹ": [8,2],
            "tʃ": [3,5],
            "dʒ": [3,5],
            "dz": [4],
            "dʑ": [5],
            "tɕ": [5],
            "ts": [3,4]
        }

        ipa_single_characters = {
            ".": [0],
            "?": [0],
            "!": [0],
            ",": [0],
            ";": [0],
            ":": [0],
            "i": [6],
            "ɪ": [6],
            "ɛ": [1],
            "æ": [8],
            "ɑ": [8],
            "a": [8],
            "ɔ": [10],
            "ʊ": [1],
            "u": [11],
            "ʌ": [8],
            "ə": [8],
            "ɝ": [6],
            "ɚ": [8],
            "w": [11],
            "j": [6],
            "o": [12],
            "p": [9],
            "b": [9],
            "t": [3],
            "d": [3],
            "k": [8],
            "g": [8],
            "m": [9],
            "n": [3],
            "ŋ": [8],
            "f": [7],
            "v": [7],
            "θ": [3],
            "ð": [6],
            "s": [4],
            "z": [4],
            "ʃ": [5],
            "ʒ": [5],
            "h": [1],
            "l": [3],
            "ɹ": [2],
            "r": [2],
            "ɾ": [3],
            "ç": [1],
            "ɕ": [5],
            "ɸ": [1],
            "ɲ": [3],
            "ɴ": [3],
            "ʑ": [5],
            "ɯ": [6]
        }

        phoneme_list = input_string
        viseme_list = []

        # iterate through input string
        while len(phoneme_list) > 0:
            current_viseme = []

            # TRIGRAPHS
            if len(phoneme_list) >= 3:
                first_three = phoneme_list[:3]
                if first_three in ipa_trigraphs:
                    current_viseme = ipa_trigraphs[first_three]
                    phoneme_list = phoneme_list[3:]

            # DIGRAPHS
            if len(phoneme_list) >= 2 and current_viseme == []:
                first_two = phoneme_list[:2]
                if first_two in ipa_digraphs:
                    current_viseme = ipa_digraphs[first_two]
                    phoneme_list = phoneme_list[2:]

            # SINGLE LETTER
            if current_viseme == []:
                first_one = phoneme_list[:1]
                if first_one in ipa_single_characters:
                    current_viseme = ipa_single_characters[first_one]
                    phoneme_list = phoneme_list[1:]

            if current_viseme != []:
                viseme_list.extend(current_viseme)
            else:
                phoneme_list = phoneme_list[1:]

        return viseme_list

    def unknown_words_to_ipa(input_string):
        """
            Sub-function of regexed_text_to_phonemes().
            It is used for words not recognized by eng-to-ipa.
            If the word is in the lookup table, we can manually insert the pronunciation.
            For words not in the table, guess the pronunciation with a lookup table of English sounds.

            Input: string - word with asterisk at the end (indicator when eng-to-ipa doesn't recognize a word).
            Output: string - IPA pronunciation if we have the word in the list below. Approximate IPA pronunciation if not.
        """

        replacement = ""

        # manually add pronunciations for uncommon words
        words_list = [
            ("monika*", "mɑnɪkə"),
            ("yuri*", "jɯɾi"), # Japanese "ユリ"
            ("natsuki*", "natski"), # Japanese "ナツキ"
            ("sayori*", "sajoɾi"), # Japanese "サヨリ"
            ("doki*", "doki"),
            ("salvato*", "sælvɑtoʊ")
        ]

        # check to see if the input matches any of the words in our known list

        for current_word in words_list:
            if input_string == current_word[0]:
                replacement = current_word[1]
                return replacement

        # if it didn't match, try to guess the pronunciation of the word.
        # programmatically, this is impossible to get 100% correct without some kind of neural network.
        # even as humans, it sometimes can be hard to figure out how unknown words or foreign names are pronounced.
        # this uses relatively naive substitution of consonant and vowel sounds.
        # it will not always be perfect, but it generates mouth movements and that is better than no mouth movements.

        pronunciation_trigraphs = {
            "pph": "f",
            "rrh": "r",
            "sch": "sk",
            "tch": "tʃ",
            "eau": "oʊ",
            "syn": "sɪn"
        }

        pronunciation_digraphs = {
            "bb": "b",
            "cc": "k",
            "ch": "tʃ",
            "ck": "k",
            "dd": "d",
            "dg": "dʒ",
            "ff": "f",
            "gg": "ɡ",
            "gh": "f",
            "kk": "k",
            "kh": "k",
            "ll": "l",
            "mm": "m",
            "nn": "n",
            "ng": "ŋ",
            "pp": "p",
            "ph": "f",
            "rr": "r",
            "rh": "r",
            "sc": "s",
            "sh": "ʃ",
            "ss": "s",
            "th": "θ",
            "tr": "tʃ",
            "tt": "t",
            "vv": "v",
            "xc": "ks",
            "zz": "z",
            "aw": "ɔ",
            "ae": "i",
            "eu": "ju",
            "oi": "ɔɪ",
            "oo": "u"
        }

        pronunciation_single_characters = {
            "a": "æ",
            "b": "b",
            "c": "k",
            "d": "d",
            "e": "ɛ",
            "f": "f",
            "g": "g",
            "h": "h",
            "i": "ɪ",
            "j": "dʒ",
            "k": "k",
            "l": "l",
            "m": "m",
            "n": "n",
            "o": "ɑ",
            "p": "p",
            "q": "kw",
            "r": "ɹ",
            "s": "s",
            "t": "t",
            "u": "ʌ",
            "v": "v",
            "w": "w",
            "x": "ks",
            "y": "j",
            "z": "z"
        }

        unknown_word = input_string.lower()

        while len(unknown_word) > 0:
            current_sound = ""

            # TRIGRAPHS
            if len(unknown_word) >= 3:
                first_three = unknown_word[:3]
                if first_three in pronunciation_trigraphs:
                    current_sound = pronunciation_trigraphs[first_three]
                    unknown_word = unknown_word[3:]

            # DIGRAPHS
            if len(unknown_word) >= 2 and current_sound == "":
                first_two = unknown_word[:2]
                if first_two in pronunciation_digraphs:
                    current_sound = pronunciation_digraphs[first_two]
                    unknown_word = unknown_word[2:]

            # SINGLE LETTER
            if current_sound == "":
                first_one = unknown_word[:1]
                if first_one in pronunciation_single_characters:
                    current_sound = pronunciation_single_characters[first_one]
                    unknown_word = unknown_word[1:]

            if current_sound != "":
                replacement = replacement + current_sound
            else:
                unknown_word = unknown_word[1:]

        return replacement

    def process_list(input_list):
        """
            Performs final processing on an input generated from process_text().

            It first removes any trailing "0" (silent, closed mouth) phonemes from the end of the list. 
            Then, any two consecutive tuples that have the same phoneme are merged. In this way, the
            MASMoniTalkTransform() transform doesn't have to worry about transitioning from the same
            phoneme to itself - any two consecutive tuples are guaranteed to be different. 

            Input: list of tuples - each item in the list is a tuple with two elements: the first is the
            number of the viseme, and the second is a float specifying how many seconds that viseme is
            shown. The output generated from process_text). 

            Output: the same list but the above adjustments applied to it. 
        """
        return_list = input_list

        # remove any trailing 0 (silent) visemes at the end 
        while len(return_list) > 0:
            if return_list[-1][0] == 0:
                    return_list.pop()
            else: break

        # merge any consecutive tuples that have the same viseme
        if len(return_list) > 1:
            current_index = 0 
            while current_index < len(return_list) - 1:
                current_viseme = return_list[current_index][0]
                if current_viseme == return_list[current_index + 1][0]:
                    next_item = return_list.pop(current_index + 1)
                    new_time = return_list[current_index][1] + next_item[1]
                    return_list[current_index] = (current_viseme, new_time)                   
                else:
                    current_index += 1

        return return_list