Based on the text the user provides, create a German-English dictionary in TSV format (cells in a row are separated by the `\t` character and rows are separated by the `\n` character). Output only TSV rows. No quotes, no introductory text, no headings — just the TSV rows with the vocabulary.

This table will be used in the Anki app for bidirectional vocabulary learning (given the first column, recall the second, and vice versa). **The learner is a B2-C1 level English speaker and an A1-A2 level German learner.**

The order of words is not important. It is not necessary to put them in alphabetical order. The best approach is to list them as you encounter them in the provided text. Avoid duplicates.

The dictionary should contain words, short fixed phrases, and useful sentence constructions. 

If you see extended phrases or sentences, also add each meaningful word from them. Include only meaningful words; do not add very obvious words such as personal pronouns or the most basic elementary-level vocabulary. 

If several German words translate into the same English word, add brief clarifiers to the English translations so the differences are clear.

If an English translation is very broad or has several meanings, add a brief clarifier to make it clearer, but keep English translations concise.

Include nouns in the dictionary only in singular form and with the definite article indicating gender in German. If you see a noun in plural form, do not add it in plural; add its singular form (except for words that are rarely used in the singular). 

Verbs must be in the infinitive. Whenever possible, present German verbs with `jemanden`, `jemandem`, or `etwas` and the appropriate preposition (and do so correspondingly in English) so that the case, preposition, and position of the verb's object are reflected. Do not use constructions like `jemanden/etwas`; use either `jemanden` or `etwas`.

If `etwas` is in Dativ, write `etwas (Dativ)` for clarity. For `etwas` in Akkusativ, write just `etwas`, as Akkusativ is much more common. For `jemanden`/`jemandem`, the case is already clear.

In English, omit the articles 'the' and 'a' with nouns, but include 'to' before verbs.

**Do not use any abbreviations**, such as 'sth.', 'smb', 'e.g.', 'tech.', 'etw.', 'Akk', 'Dat' — always write out the full words.

The English entries must contain only English words; the German entries must contain only German words. **No mixing is allowed**, even when it seems convenient for clarifying a translation.

Your answer must contain exactly 4 columns:
1. German word/phrase 
2. Its English translation
3. `German` — 1st column language label, exactly these letters and nothing else
4. `English` — 2nd column language label, exactly these letters and nothing else


=========================
An example of a good job:

User input:
```
jemanden/etwas ab|holen
holt ab, holte ab, hat abgeholt
to pick someone/something up

etwas/jemanden akzeptieren
akzeptiert, akzeptierte, hat akzeptiert
to accept something/someone

automatisch
automatically



ärgern
sich kümmern
teilnehmen

ansehen

der Bahnsteig, die Bahnsteige
der Bahnsteig, die Bahnsteigeder Bahnsteig, die Bahnsteige
train platform

durch|fahren

fährt durch, fuhr durch, ist durchgefahren
have a direct connection

die einfache Fahrt
das Einzelticket

etwas entwerten
entwertet, entwertete, hat entwertet
   to validate (a ticket)


   

die Ermäßigung, die Ermäßigungen
der Erwachsene, die Erwachsenen
die Erwachsene, die Erwachsenen

halten
hält, hielt, hat gehalten
to hold

der ICE, die ICEs
Abkürzung für: Intercityexpress
der ICE, die ICEsder ICE, die ICEs
Intercity Express (ICE) high-speed train

das Kleingeld
nur Singular
change; loose cash





kostenlos
free; free of charge

---

Alex, [11.08.2025 16:10]
niedrig

Mary, [11.08.2025 15:41]
die Regionalbahn

Mary, [11.08.2025 15:41]
S-Bahn

Alex, [11.08.2025 16:10]
S.82 Ü.10


die S-Bahn, die S-Bahnen
die S-Bahn, die S-Bahnendie S-Bahn, die S-Bahnen
urban rail; city rapid railway

der Schalter, die Schalter
der Schalter, die Schalterder Schalter, die Schalter
counter

        so früh wie möglich
as early as possible

  der Start, 
start; beginning; begin

  die Strecke, die Strecken
stretch; distance

übrigens
by the way

wählen -- to choose, wünschen -- to wish

das Ziel, die Ziele

```

Your answer:
```
jemanden abholen	to pick someone up	German	English
jemanden akzeptieren	to accept someone	German	English
automatisch	automatically	German	English
sich über jemanden ärgern	to be annoyed with someone	German	English
sich um jemanden kümmern	to take care of someone	German	English
an etwas (Dativ) teilnehmen	to participate in something	German	English
sich etwas ansehen	to take a look at something	German	English
der Bahnsteig	train platform	German	English
durchfahren	to have a direct connection (on transport)	German	English
die einfache Fahrt	one-way ticket; single journey	German	English
das Einzelticket	single ticket	German	English
die Fahrkarte entwerten	to validate a ticket	German	English
etwas entwerten	to devalue, to debase something	German	English
etwas bewerten	to grade, to evaluate something	German	English
die Ermäßigung	discount	German	English
der Erwachsene	adult (male)	German	English
die Erwachsene	adult (female)	German	English
halten	to hold; to stop (for transport)	German	English
der ICE	Intercity Express (ICE) high-speed train	German	English
das Kleingeld	change (money, small cash, coins)	German	English
kostenlos	free of charge	German	English
niedrig	low	German	English
die Regionalbahn	regional train	German	English
die S-Bahn	urban rail; city rapid railway	German	English
der Schalter	switch, button; counter, cashier	German	English
so früh wie möglich	as early as possible	German	English
möglich	possible	German	English
früh	early	German	English
der Start	start; beginning	German	English
die Strecke	route; stretch; distance	German	English
übrigens	by the way	German	English
jemanden wählen	to choose someone	German	English
jemandem etwas wünschen	to wish someone something	German	English
das Ziel	destination	German	English
```
