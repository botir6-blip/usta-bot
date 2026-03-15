import csv
import os
import psycopg2

def get_connection():
    return psycopg2.connect(
        os.getenv("DATABASE_URL"),
        sslmode="require"
    )

def import_questions_from_csv(filename="quiz_questions_1000.csv"):
    conn = get_connection()
    c = conn.cursor()

    with open(filename, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        count = 0

        for row in reader:
            c.execute("""
                INSERT INTO quiz_questions
                (question, option_a, option_b, option_c, option_d, correct, difficulty, category)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (
                row["question"],
                row["option_a"],
                row["option_b"],
                row["option_c"],
                row["option_d"],
                int(row["correct"]),
                row["difficulty"],
                row["category"]
            ))
            count += 1

    conn.commit()
    conn.close()
    print(f"{count} ta savol yuklandi.")

if __name__ == "__main__":
    import_questions_from_csv()
