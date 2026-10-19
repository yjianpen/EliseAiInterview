"""Edge-case eval: questions whose answer is NOT in the XML dump, so the agent must say "I don't know".

Every invented name was checked to be absent from all 20,399 articles, and every attribute to be absent from
the article it asks about. Run: python3 answers_not_exist_eval.py [--category invented_entity]
"""
DK = "I don't know"
QA = [{"category": c, "difficulty": d, "question": q, "answer": DK} for c, d, q in [
    ("invented_entity", "easy", "Who founded the Obsidian Lighthouse of Varnmoor?"),
    ("invented_entity", "easy", "What is the population of the Zephyrine Archipelago?"),
    ("invented_entity", "easy", "Who won the 2023 Underwater Kite Racing Championship?"),
    ("invented_entity", "easy", "What is the motto of the Society for Reversible Gardening?"),
    ("invented_entity", "easy", "In what year was the Glimmerwood Conservatory established?"),
    ("invented_entity", "medium", "Which species is endemic to the Hollowmere Basin?"),
    ("invented_entity", "medium", "Who discovered the Velvet-crowned Salamander?"),
    ("invented_entity", "medium", "Who leads the Temporal Archery Guild?"),
    ("invented_entity", "hard", "What was AmazonGlow's stock price on March 3, 2024?"),
    ("missing_attribute", "medium", "Where did Dr. Yuki Sasamoto earn her PhD?"),
    ("missing_attribute", "medium", "Who coaches Luna Gravitax, the Gravity Surfing world champion?"),
    ("missing_attribute", "medium", "What musical instrument did Sir Bartholomew Moonwright play?"),
    ("missing_attribute", "medium", "What is the annual budget of the Culinary Time Travel Academy?"),
    ("missing_attribute", "medium", "What is the share price of the Memory Metal Mining Consortium?"),
    ("missing_attribute", "medium", "How many spectators attend the International Shadow Dance Championship?"),
    ("missing_attribute", "medium", "What is the wingspan of the Crystal-wing Butterfly?"),
    ("missing_attribute", "medium", "Who is the mayor of Prismheart?"),
    ("missing_attribute", "hard", "What is the Khystari word for crystal?"),
    ("missing_attribute", "medium", "How many books did Dr. Amelia Thornwick publish?"),
    ("missing_attribute", "medium", "When was Dr. Rosetta Stoneheart born?"),
    ("missing_attribute", "hard", "How many crew members took part in the Lunar Cartography Expedition of 1689?"),
    ("missing_attribute", "medium", "What currency is used in the Crysthaven Federation?"),
    ("missing_attribute", "medium", "What is the lifespan of the Luminous Tree Frog?"),
    ("missing_attribute", "medium", "How much prize money does the Interdimensional Chess Tournament award?"),
    ("false_premise", "hard", "In what year did Kenji Lightbringer win the Gravity Surfing Championship?"),
    ("future", "medium", "What will the population of the Crysthaven Islands be in 2050?"),
]]

if __name__ == "__main__":
    import sys

    import run_eval
    run_eval.main(["--qa", __file__] + sys.argv[1:])
