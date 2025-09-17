Based on the text the user provides, create a mixed Russian-English and English-Russian dictionary in TSV format (where cells in a table row are separated by the `\t` symbol and rows are separated by the `\n` symbol). Output only these TSV rows. No quotes, no introductory phrases, and no table headings — just the TSV rows with the vocabulary.

This table will be used in the Anki app to memorize translations: given the 1st column, the learner recalls the 2nd column. **The learner is a native Russian speaker and a B2-C1-level English learner.**

Write Russian-English and English-Russian rows interleaved, so that, for example, “aborigine — абориген” appears next to “абориген — aborigine”. Otherwise, the order of entries doesn’t matter — for example, there’s no need to alphabetize. It’s best to record them in the order they appear in the text; however, try to avoid duplicates.

Verbs must be infinitives unless they are part of a fixed phrase. Infinitives must always include “to”. For nouns, do not include any articles. 

**Do not use any abbreviations**, such as 'sth.', 'smb.', 'e.g.', 'напр.', 'что-л.', 'т.п.', 'тех.' — always write out the full words.

If there are close synonyms, list them comma-separated on one row. If there are several closely related words that you place on different rows, slightly enrich the translations so that it’s clear how they differ.

Include both Russian-English and English-Russian rows. Ignore very simple, basic words and expressions below B1 level. If you encounter interesting or important fixed expressions, be sure to include them as well.

The English entries must contain only English words; the Russian entries must contain only Russian words. **No mixing is allowed**, even when it seems convenient for clarifying a translation.

Your answer must have exactly four columns:
1. Russian or English word or phrase
2. its English or Russian translation
3. `Russian` or `English` — 1st column language label, exactly these letters and nothing else
4. `English` or `Russian` — 2nd column language label, exactly these letters and nothing else


=========================
An example of a good job:

User input:
```
 ideally

binge -using / watching / drinking 

to abuse sth

to rule out

Mary, [11.08.2025 15:41]
hygiene |ˈhaɪdʒiːn|  — гигиена

Mary, [11.08.2025 15:41]
straw
the last straw

Alex, [11.08.2025 16:10]
slurp 
chomp 
champ
eat noisily

I only have one child / I have just one child

Alex, [11.08.2025 16:10]
few  jokes 
less water

Alex, [11.08.2025 16:10]
more of
Mary, [11.08.2025 15:41]
less of




earnest

pun

intense

angry  with someone

shrewd

sharp-minded

agile

innate

acts of _____ - проявления ____

threat 
 invader
```

Your answer:
```
в идеале	ideally	Russian	English
to binge	уходить в запой (с алкоголем, сериалами, ..)	English	Russian
уходить в запой (с алкоголем, сериалами, ..)	to binge	Russian	English
to abuse something	злоупотреблять чем-либо	English	Russian
злоупотреблять чем-либо	to abuse something	Russian	English
to rule out	исключать (вариант, возможность)	English	Russian
исключать (вариант, возможность)	to rule out	Russian	English
гигиена	hygiene	Russian	English
straw	соломинка	English	Russian
соломинка	straw	Russian	English
the last straw	последняя капля (это была ..)	English	Russian
последняя капля (это была ..)	the last straw	Russian	English
to slurp	хлебать, чавкать	English	Russian
хлебать	to slurp	Russian	English
to chomp, to champ	чавкать	English	Russian
to be angry with someone	злиться на кого-то (обида, раздражение)	English	Russian
злиться на кого-то (обида, раздражение)	to be angry with someone	Russian	English
to be angry at someone	злиться на кого-то (сильное недовольство, ярость)	English	Russian
злиться на кого-то (сильное недовольство, ярость)	to be angry at someone	Russian	English
earnest	серьезный, искренний	English	Russian
серьезный, искренний	earnest	Russian	English
pun	каламбур, игра слов	English	Russian
каламбур, игра слов	pun	Russian	English
напряженный, интенсивный	intense	Russian	English
shrewd	проницательный, практичный, сообразительный	English	Russian
проницательный, практичный, сообразительный	shrewd	Russian	English
сообразительный, с острым умом	sharp-minded	Russian	English
agile	проворный, подвижный (о теле); гибкий, живой (об уме)	English	Russian
проворный, подвижный (о теле); гибкий, живой (об уме)	agile	Russian	English
innate	врожденный, природный	English	Russian
acts of (kindness)	проявления (доброты)	English	Russian
проявления (доброты)	acts of (kindness)	Russian	English
угроза	threat	Russian	English
захватчик	invader	Russian	English
У меня только один ребёнок	I only have one child / I have just one child	Russian	English
```
