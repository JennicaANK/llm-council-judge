import pandas as pd
df = pd.read_excel("CS180_DataCollection_1500.xlsx")
questions = df["question_text"].dropna().str.strip()
questions = questions[questions != ""]
questions.to_csv("questions.txt", index=False, header=False)