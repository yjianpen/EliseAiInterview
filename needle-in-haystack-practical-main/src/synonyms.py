"""Edge-case eval: questions that name entities by an alias or use synonyms of the article's wording.

Aliases come from the articles themselves (also_known_as, abbreviation, binomial names); paraphrases swap
the article's verb or noun (founded -> started, population -> how many people live). Every answer was
checked against the article text. Run: python3 synonyms.py [--category abbreviation]
"""
QA = [{"category": c, "difficulty": d, "question": q, "answer": a} for c, d, q, a in [
    ("alias", "medium", "When did the Great Scholarly Convergence take place?", "267–270 CE"),
    ("alias", "medium", "In which city did the Great Scholarly Convergence happen?", "Alexandria, Egypt"),
    ("alias", "medium", "In what year did the Celestial Symphony occur?", "1472"),
    ("alias", "medium", "In which region did the Magnetic Dance Movement take place?", "Central America"),
    ("alias", "medium", "How far do Prismatic Wing Butterflies travel on their migration?", "2,000 kilometers"),
    ("abbreviation", "medium", "Who founded the CTTA, the culinary school specializing in historical cuisine?", "Professor Temporal Delicious"),
    ("abbreviation", "medium", "What is the motto of the IIA in Paradoxopolis?", "Building Beyond Reality"),
    ("abbreviation", "medium", "Who founded the IAES, the society that exhibits art invisible to the naked eye?", "Dr. Spectrum Unseeable"),
    ("abbreviation", "medium", "Where is the MFWF wrestling federation headquartered?", "Foam City Arena"),
    ("abbreviation", "medium", "Who leads the CCSL, the professional cloud-shaping league?", "Dr. Nimbus Sculptor"),
    ("scientific_name", "medium", "What is the conservation status of Hyla bioluminescens?", "Critically Endangered"),
    ("scientific_name", "medium", "Who first identified Bryum magneticus?", "Dr. Compass Fieldwright"),
    ("scientific_name", "medium", "In which country was Orchidaceae gravitensis discovered?", "Peru"),
    ("scientific_name", "hard", "Who first documented the migration of Lepidoptera crystallinus?", "Dr. Spectrum Wingfield"),
    ("paraphrase", "easy", "By what name is Aethermist Valley known among the Norathi?", "Skyfather's Breath"),
    ("paraphrase", "easy", "How many people live on the Crysthaven Islands?", "45,000"),
    ("paraphrase", "easy", "What is the tallest mountain in the Crysthaven Islands?", "Mount Prismheart"),
    ("paraphrase", "medium", "How high does the tallest peak of the Crysthaven Islands rise, in meters?", "423"),
    ("paraphrase", "easy", "Who is the chief librarian at the library in Loftington where books float?", "Ms. Celestia Pageturner"),
    ("paraphrase", "easy", "Who started the Festival of Floating Lanterns?", "Kenji Lightbringer"),
    ("paraphrase", "easy", "When did the Levitating Library of Loftington open?", "1823"),
    ("paraphrase", "easy", "Who created the Gravity Surfing Championship?", "Cosmos Wavewright"),
    ("paraphrase", "easy", "Who is the reigning Interdimensional Chess champion?", "Quantum Knightsworth"),
    ("paraphrase", "medium", "Who unearthed Mnemonic Ore?", "Dr. Petra Rememberstone"),
    ("paraphrase", "medium", "How long is Aethermist Valley from end to end?", "23 kilometers"),
]]

if __name__ == "__main__":
    import sys

    import run_eval
    run_eval.main(["--qa", __file__] + sys.argv[1:])
