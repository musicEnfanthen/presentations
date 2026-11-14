# Speaker notes – AWG graph talk (genetics2026)

Stand: final pass, 13.11.2026; written back into `build/build_deck.py`.

Spoken text: 3147 words ≈ 24.2 min at 130 wpm (cues not counted); target times = spoken time + about 45 s for pauses and pointing (slides 2, 5–7, 13–16), sum 25:00, no reserve.

Conventions:

- `[…]` = stage direction or cue, not spoken. `[Q: …]` = open question to you, delete when settled.
- Timing header per slide: `[label] Target time (cumulative of 25:00)`. Times follow the word count of each slide; they go into `build_deck.py` at write-back.
- ALT TEXT paragraphs are not in this file. At write-back they move out of the notes and become real alt text (`descr`) on the images and diagram groups in `build_deck.py`.
- Terms used throughout: edition complex, version (Textfassung), sketch / sub-sketch, paratext, row table, uncertainty tag, precedes / concomitates (lower case, as relation names), the generated / curated layer, source descriptions.

## Slide 1 – Compositional Processes as Graph / Semantic Modelling and Terminology in the Anton Webern Gesamtausgabe (AWG)

[Title] Target time: 0:40 (cumulative 0:40 of 25:00)

Thank you for the kind introduction, and thank you for the invitation, especially since our project, the Anton Webern Gesamtausgabe, is not a genetic edition in the strict sense. But Webern can't be edited without addressing or understanding his complex compositional processes. So, as a word of caution, the "genetic" approach I present is more a pragmatic one, not a fully fledged theory of genetic criticism – I hope it offers some insights nonetheless.

## Slide 2 – The sources show a network; a printed edition needs an explicit order / Research problem

[Research problem] Target time: 1:30 (cumulative 2:10 of 25:00)

Let me put the talk's question first.

[Pause, let the slide speak.]

As we have seen in several papers today already, compositional processes rarely form a linear sequence. Sketches overlap and are spread over sketchbooks and loose sheets; earlier stages of a work may be scattered across manuscripts, places or years. In short, the surviving sources most often form a network of relations.

However, editions in a traditional sense, following the page-based linearity of the book, had to choose some order. Digital editions set out to overcome this linearity with hypertextuality. But do they really? Don't we still tend to streamline writing layers and editorial findings into our narratives (a curated "pathway" through the edition as Kepper/Pugin called it some years ago)? Open findings, discarded, overwritten, erased attempts, ruptures or uncertainty remain a challenge for a digital environment that strives for completeness and explicitness.

So: how can a digital edition represent such non-linear processes – in other words, how do we keep open what cannot be finally described or decided, and yet hold it in a formal model? That is this talk's question. As you may have guessed from the slide, our approach to it is a graph-based one.

## Slide 3 – The AWG distinguishes three forms of edition, by transmission and use / The Anton Webern Gesamtausgabe

[The AWG and its editions] Target time: 1:20 (cumulative 3:30 of 25:00)

But first, a word on the edition project itself. The Anton Webern Gesamtausgabe is a historical-critical complete edition of Anton Webern's compositions, in print and online. It distinguishes three forms of edition, depending on how the sources have come down to us and on the intended usage: work, text and sketch editions.

Work editions present the compositions published in Webern's lifetime or intended for publication: op. 1 to 31, and his arrangements of other composers' works. Text editions present versions that go beyond a sketch but were not concluded in print: study compositions, fragments, earlier versions of published works. Both edit a version of the musical text – in German, a "Textfassung". A version is not a document: it is a state of the musical text, attested by one or more sources.

Sketch editions edit Webern's sketches – mostly in pencil, and most often, but not always, connected to a Textfassung.

The three forms also differ in detail and standardisation: sketch editions come close to diplomatic transcription; work editions standardise most, towards a performable score.

## Slide 4 – The AWG graph combines generated data with curated editorial assertions / The AWG and its graph

[The AWG and its graph] Target time: 0:45 (cumulative 4:15 of 25:00)

In its online edition, the AWG adds the graph as a semantic view of these materials. In its current state, which is still in development (and unfortunately not publicly available yet), it combines two layers. One layer is automatically generated from the edition's structured data: hierarchy, sources, folios, placements, and relations that follow from the sketch sigla numbering. A curated layer holds what only editors can assert: evidence-based order, or uncertainty.

Both layers are described by one RDF ontology which together with the data can be queried with SPARQL and exported as Turtle.

## Slide 5 – Generated from the edition data alone, op. 25 falls into three "islands" / Graph view: op. 25

[Graph view: op. 25 (1/3)] Target time: 0:35 (cumulative 4:50 of 25:00)

So to give you an example upfront, this is the graph view of Webern's op. 25 (Three songs after poems by Hildegard Jone), with the catalogue numbers M 317, M 322 and M 321 standing for these three songs.

In the automatically generated layer, you can see the three "islands", one per song, ordered by numbering of their sketches. The row table is there [red mark], but without any genetic relation.

## Slide 6 – The curated layer links the three songs in one chain / Graph view: op. 25

[Graph view: op. 25 (2/3)] Target time: 0:30 (cumulative 5:20 of 25:00)

In the curated layer, the editors' assertions add a connection [red marks] from M 317 Sk4 to M 321 Sk1, then M 321 Sk9 to M 322 Sk1. Webern sketched the third song of the opus, M 321, before the second, M 322 – together with the row table, which is now part of many more relations.

## Slide 7 – The combined layers show where editorial judgment becomes explicit / Graph view: op. 25

[Graph view: op. 25 (3/3)] Target time: 0:30 (cumulative 5:50 of 25:00)

When we combine both layers, the "islands" are still there: within each song, the numbering already gives an order. The connection across the songs [red mark] is what only the curated layer brings in. That difference is where the editorial judgment becomes explicit – and the laboratory for the rest of this talk.

[Not spoken: the screenshots come from the app's graph view, filtered with the SPARQL query in build/op25-demo-query.rq.]

## Slide 8 – The categories come from Webern's documents, not from theory / Terms from the material

[Terms from the material] Target time: 1:35 (cumulative 7:25 of 25:00)

Before we look into Webern's sketches, let me take a few minutes for the model behind this graph: its terms, its classes, its relations, and how it relates to formal standards.

So, where do the terms of the model come from? Not from a theory of genetic criticism, but from editorial practice: they name what the editors find in Webern’s documents, as recorded in the AWG’s source descriptions.

A sketch is a unit of writing the editors identify on the page and number: Sketch 1, Sketch 2, and Sketch 2.1 for a sub-sketch. A version – the Textfassung from before – is a state of the musical text, numbered TF1, TF2. Paratexts are everything on the page that accompanies the music: title, dating, pagination, also instrumentations if not the same complex. The row table is Webern’s own sheet with the forms of the twelve-tone row – and, as the graph view showed, part of Webern's compositional process. The edition complex comprises everything relevant to an edition of a composition – single, or composite like op. 25. It is named by opus number or by M number from Hans Moldenhauer’s catalogue.

Below each term, you see how it occurs in op. 25 – the example from the graph view.

## Slide 9 – Editorial terms become classes; uncertainty becomes a tag / From term to class

[From term to class] Target time: 1:25 (cumulative 8:50 of 25:00)

In the source descriptions, these terms are used as editors use them: flexibly, and explained in prose. A graph needs more. It has to say what belongs to a category, and how the categories relate to each other. So each term becomes a class.

The first question was: what do a sketch and a paratext have in common? Both are written on a page, and both have a place in the compositional process – a title or a dating is written at some point, too. So the superclass is Inscription: everything written on a document that we can place in that process. Sketch and Paratext are its subclasses. Under Sketch, there are two more specific classes: the row table and the continuity draft.

Uncertainty is not a relation of its own. An earlier draft had a relation "concomitates unsure". Now an editorial statement carries an uncertainty tag: certainty, uncertain. Without the tag, the statement counts as certain.

Some terms of the edition have no class yet like "study composition" and "ink draft", but we are in the process of including them.

## Slide 10 – Two relations link inscriptions: a sequence, or mutual influence / Genetic relations

[Genetic relations] Target time: 1:40 (cumulative 10:30 of 25:00)

Inscriptions placed in the process need relations between them. The model has two – precedes and concomitates.

"precedes" marks a temporal order that the evidence supports: A was started before B. It says nothing about the end – overlap is allowed, because Webern often went back to an earlier sketch while working on a later one. The relation is transitive. (Cf. CIDOC CRM's P176 "starts before the start of")

"concomitates" is a different kind of statement. A and B were written alongside each other, and each shaped the other: a change in one is taken up in the other. Which came first cannot be decided – so the relation records the influence instead of marking an order. It implies overlap in time; it is symmetric, and not transitive. (Cf. CIDOC CRM's P174 "starts before the end of")

For precedes, the model can also record the kind of evidence. precedesScripture rests on the writing: position on the page, overlay, writing instruments, layers of correction. precedesContent rests on the musical content: the later inscription takes over changes made in the earlier one. In op. 25, the editors assert precedesScripture between Sketches 1 and 2 of M 317 – you will see it on the page – and precedesContent between Sketches 2 and 3. Plain precedes leaves the evidence open.


## Slide 11 – For now, the model is domain-specific, with links to standards / Standards and alignments

[Standards and alignments] Target time: 1:15 (cumulative 11:45 of 25:00)

How does this relate to standards? For now, the model is domain-specific: built for Webern’s sources and the AWG’s needs. Where existing models offer related concepts, we point to them – LRMoo for work, expression and item, CIDOC CRM for the temporal reading of the two relations you just saw. The connections to those standards are links, rdfs:seeAlso, not subclasses: a subclass would commit us to all the semantics the standard implies which do not always fit. Where single terms fit exactly, we use them directly: from Dublin Core for parts and wholes, from SKOS for concept schemes, from PROV for attribution. MEI is not integrated yet.

One example shows why we keep the distance for now. LRMoo separates content and object, the expression and the item that carries it. For a sketch, that cut runs right through the argument: relating sketches draws on what they contain and on how they stand on the page – both at once, as you will see shortly.

## Slide 12 – The model could transfer; the pipeline cannot / What transfers

[What transfers] Target time: 1:30 (cumulative 13:15 of 25:00)

What of this would transfer to other editions? Domain-specific does not mean Webern-specific. I would separate two things.

Ideally, the core is portable. Inscription, Document, Folio and Placement describe what is written where: on which object, which leaf and which side, which staves and measures. Placement is a node of its own, so that one sketch can run across several pages and keep its place on each. And the two relations link inscriptions – with branches and parallels, not one sequence. Editions of sketches and drafts will likely come back to these distinctions in one way or another.

Tied to the AWG is the pipeline. The generator reads the edition’s own data: source descriptions, sheet IDs, and M numbers from Moldenhauer’s work catalogue. And it reads numbering as process: Sketch 1 precedes Sketch 2, Sketch 2.1 concomitates with Sketch 2. That is often right – but it remains our convention, and a claim without explicitly modelled evidence type. Relations across complexes come only from curation.

So, as the bottom line says: transfer is plausible, but untested. I would be very interested to hear whether these classes fit the material you work on.

## Slide 13 – (no title placeholder) / Overview: fol. 38v

[Overview: fol. 38v] Target time: 1:00 (cumulative 14:15 of 25:00)

So much for the model – now to Webern’s sketches. This is folio 38 verso of his third sketchbook, with the first sketches for "Wie bin ich froh!" M 317, the first song of op. 25. The boxes and numbers are ours: the AWG distinguishes fifteen sketches on this one page.

They do not follow the reading order. And the page holds more than musical content, namely the paratexts, dotted here – a title, a dating, a page number. One layer of the paratexts even belongs to another work: at the top, Webern had prepared the systems for the Concerto for Nine Instruments, op. 24 – and then sketched op. 25 into them.

Let's dive into the top three systems [red dashed frame].

## Slide 14 – On one sketchbook page, both relations are at work / Example: M 317, fol. 38v

[Example: M 317] Target time: 2:20 (cumulative 16:35 of 25:00)

Here are the top three systems in the AWG's diplomatic transcription. Normally, the edition gives each sketch on its own sheet; here I have put three of them back on one page together.

[Point to Sk1.] In the middle, Sk1: a four-note figure, the opening of the voice part, in a first draft, deleted by a hook.

[Point to Sk2.] To its left, Sk2: a twelve-tone row, in two attempts. The first, row A, breaks off after five notes; another hook marks it as deleted. Row B completes the row. Why does Sk1 come first, although it stands to the right? Look at the right end of Sk2 [red mark]: the writing is squeezed together. Sk2 ran into the space that Sk1 already occupied. That is, in our terminology, precedesScripture: an order from the writing.

[Point to Sk2.1.] On the right, Sk2.1 turns the row of Sk2, in the rhythm of Sk1, into a melody with text. The commentary says that row B of Sk2 was written "in dynamic alignment" with Sk2.1 and its variants. You can see it in one note [green marks]: in bar 2 of Sk2.1, Webern brackets the g – a sign for its deletion – and goes on with f sharp; in row B, he writes f sharp over the g – the grey note is the overwritten one. The same decision, in both places. Each shaped the other; it cannot be decided which came first. In the model, that is concomitates.

So one page holds both: an order inferred from the writing, and an exchange that no order captures. Even the dating, 4 July 1934, is modelled this way: it concomitates with Sk1 and with Sk2, because the editors cannot say with which of the two it was written.

## Slide 15 – A process Webern kept reordering, and then dropped, becomes graspable / Exploring the graph: M 307

[Exploring the graph: M 307] Target time: 1:25 (cumulative 18:00 of 25:00)

A second example, from the beginnings of our work with the idea of graphs: a sketch graph of M 307, which we drew by hand in 2019. Here the process is even less linear than in op. 25.

Webern had not settled the scoring: He starts for four voices [top band], tries out row variants [left], changes to three voices [middle], and ends with voice and piano [bottom right]. He keeps reordering – and in the end he abandons the piece.

On paper, these sketches are spread over three pages, and their order is anything but obvious – even if you took the numbering as chronological order, it would not tell you which sketch belongs to which scoring. Put as a graph, the process becomes something you can place: you see which sketch leads where, across the changes of scoring, and where the order stays open.

For our editors, that was the point of drawing it: it made a process we could not yet describe in words graspable – and it showed us what a model would have to hold.

## Slide 16 – The graph shows patterns the commentary spreads out – and gaps it hides / Exploring the graph: M 317

[Exploring the graph: M 317] Target time: 1:50 (cumulative 19:50 of 25:00)

What does the graph add to the critical commentary? Not new facts – everything here was asserted by the editors. But it shows them differently. Three things, back on the first sketches of M 317.

Clusters. Sk2.1 and its variants all concomitate – with Sk2.1, and through it with Sk2. In the commentary, that is five separate entries, each saying "in dynamic alignment with". In the graph it is one cluster [point to the shaded area]: a compositional work phase at a glance.

Paths. The precedes chain runs from Sk1 through Sk4 – and on into M 321, the third song, as in the graph of op. 25. You follow a path instead of reassembling it from page references.

Gaps. Here the graph and the commentary disagree. The commentary says – as we just saw – that Sk2.1 builds on the rhythm of Sk1 – but there is no edge between them yet [red dotted line]; Sk2.1 hangs on Sk1 only by way of Sk2. And Sk2.1.2 is "presumably" the continuation of Sk2.1.1 – but the statement carries no uncertainty tag, so it counts as certain. Reading entry by entry, you see neither. In the graph, a missing relation becomes visible, and untagged statements can be listed and checked against the commentary.

So the graph does not discover anything by itself. It makes commentary and data comparable – which brings us to the frictions.

## Slide 17 – Where model and data diverge, each gap is information / Frictions: model vs. data

[Frictions: model vs. data] Target time: 2:15 (cumulative 22:05 of 25:00)

These frictions are of another kind than the gaps we just saw: not between commentary and graph, but between model and data. They run in two directions [point to the two columns].

Where the model lags behind the data, claims stay in prose. The source descriptions record on which staves a sketch stands and which measures it covers – but in their own notation: “1c to 3c”, or labels like 1A and 1B for discarded attempts. The graph carries these as strings, so a query cannot see them; to change that, the model needs terms for parts of a staff and for discarded measures. Writing instruments – pencil, ink, crayon – are not in the model yet either, although precedesScripture rests on them. These gaps we can and will close.

Where the data lag behind the model, the decision lies with the editors, not with the model. Sketchbook 3 is described twice, as two excerpts, because each complex describes only its own pages. That needs alignment in the data at some point. 29 sketches are still placeholders, “Sk##”: their number awaits an editorial decision. And some datings have no year – “M. am 30. IX.“. Webern left it open. The model keeps the paratext as it stands, and the year would come in as the editors’ own claim – tagged as uncertain, not stored as fact.

The generator reports such cases instead of closing them silently: twelve warning rules, placeholder and incompleteDate among them.

So each gap is information – about the model, or about the evidence. A string shows where the model still lacks terms; a placeholder, where a decision is pending; a warning, where the graph refuses to claim more than the evidence allows.

## Slide 18 – The mismatch between model and data is the analytical gain / Conclusion and outlook

[Conclusion and outlook] Target time: 1:55 (cumulative 24:00 of 25:00)

Back to the opening question: can the graph keep open what cannot be decided, and yet hold it in a formal model? Partly. The model has means for openness: concomitates instead of an invented order, plain precedes where the evidence is not specified, an uncertainty tag on a statement. Where it has none yet, openness survives as strings and gaps – readable, but not queryable. And where the generator reads numbering as process, it closes more than the editors claimed. Three conclusions follow.

First: layers show where editorial judgment becomes explicit. The generated layer already rests on editorial decisions – the numbering, the source descriptions – but leaves them implicit; the curated layer states what editors assert. In op. 25, the difference is the chain across the songs: the editors' argument, made visible.

Second: warnings show where the data are open or disagree. The generator reports instead of silently repairing.

Third: model and data are written side by side – concomitant, in the sense of our own relation. The model was revised wherever the data resisted, and the data will be revised wherever the model shows gaps. In that sense, “compositional processes as graph“ also means: the graph itself is in process.

Next steps: the editorial statements will move into named graphs, so that, for example, the ink and pencil layers of a sketch can be kept apart – one of the gaps we saw. And persons and archives, so far only open questions, will become part of the model.

## Slide 19 – If model and data shape each other, the graph is also our construction / Closing question

[Closing question] Target time: 1:00 (cumulative 25:00 of 25:00)

I would like to end with a question rather than a result.

If model and data shape each other – if they are, in our own term, concomitant – then the graph does not simply reflect Webern's compositional processes, read off the documents. It is also our construction: our numbering, our evidence types, our decisions about what counts as a relation. So: whose process does the graph show – Webern's, or ours?

The second question looks outward. Every formal model is a kind of translation. We have seen it in this talk: editorial terms into classes, observations into edges etc. Each step keeps something, and loses something. So: how much of (Webern’s) compositional processes survives translation into formal models?

I look forward to your answers – and to your material. Thank you.

[Stage: stay on this slide during the discussion; go to the next slide (contact) only at the very end.]

## Slide 20 – Thank you / Contact

[Contact] Target time: 0:00 (cumulative 25:00 of 25:00)

[Stage: show only after the discussion, or when the chair closes the session; no spoken text. The closing question (previous slide) stays up during the Q&A.]
