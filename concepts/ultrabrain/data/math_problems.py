"""Deterministic fixture for verified math generation."""


PROBLEMS = [
    {"problem": "2 + 3 * 4", "answer": "14", "status": "solved"},
    {"problem": "2*x + 3 = 11", "answer": "x=4", "status": "solved"},
    {"problem": "x + 7 = 12", "answer": "x=5", "status": "solved"},
    {"problem": "3 = x + 1", "answer": "x=2", "status": "solved"},
    {"problem": "x + 3 = 2*x + 1", "answer": "x=2", "status": "solved"},
    {"problem": "2*x + 3 = x + 10", "answer": "x=7", "status": "solved"},
    {"problem": "-x + 4 = 1", "answer": "x=3", "status": "solved"},
    {"problem": "x/2 + 3 = 5", "answer": "x=4", "status": "solved"},
    {"problem": "x + 1 = x + 2", "answer": "no solution", "status": "contradiction"},
    {"problem": "x + 1 = x + 1", "answer": "all real numbers", "status": "identity"},
]


def default_problems():
    return [dict(item) for item in PROBLEMS]


def split(problems=None, holdout_every=4):
    problems = list(problems or default_problems())
    train, holdout = [], []
    for i, item in enumerate(problems, start=1):
        (holdout if i % holdout_every == 0 else train).append(dict(item))
    return train, holdout
