import random
import json
import os

levels = {}
with open("levels.json", "r", encoding="UTF-8") as j:
    levels = json.load(j)


def select_image(level: int, item_type: str | None = None) -> dict:
    """select an image set from the database depending on user level

    Args:
        type (str): literal "rock" / "mineral"
        level (int): the level of the user

    Returns:
        dict: A dictionary of answer and image list
            ```
            {"answer": "...", "imgs": ["path/to/img",...]}
            ```
    """
    if item_type is None or item_type not in ["rocks", "minerals"]:
        item_type = random.choice(["rocks", "minerals"])
    difficulty = str(random.randint(1, min(level, levels["max_level"])))
    while len(levels[difficulty][item_type]) < 1:
        difficulty = str(random.randint(1, min(level, levels["max_level"])))
    answer = random.choice(levels[difficulty][item_type])
    imgs = [f"imgs/{item_type}/{answer}/{x}" for x in os.listdir(f"imgs/{item_type}/{answer}")]
    random.shuffle(imgs)
    return {"answer": answer, "imgs": imgs}
    
