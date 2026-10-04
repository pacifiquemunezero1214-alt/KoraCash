import sqlite3
from datetime import datetime

DATABASE = "koracash.db"

VIDEOS = [
    {
        "title": "Clean Hands Help Prevent the Flu",
        "description": "Learn how proper hand washing helps prevent the spread of infectious diseases such as flu.",
        "video_url": "https://www.youtube.com/watch?v=XHISh559oho",
        "reward": 1000,
        "duration_seconds": 63,
        "category": "Health",
        "source": "CDC",
        "license": "Public Domain",
    },
    {
        "title": "Social Determinants of Health",
        "description": "A short CDC educational video about social determinants of health and public health outcomes.",
        "video_url": "https://www.youtube.com/watch?v=894v2WnSiSI",
        "reward": 1000,
        "duration_seconds": 66,
        "category": "Health",
        "source": "CDC",
        "license": "Public Domain",
    },
    {
        "title": "Wash Your Hands",
        "description": "A short educational video explaining proper hand washing with soap and clean running water.",
        "video_url": "https://www.youtube.com/watch?v=qJG72sycQB8",
        "reward": 1000,
        "duration_seconds": 30,
        "category": "Health",
        "source": "CDC",
        "license": "Public Domain",
    },
    {
        "title": "Hand Hygiene Saves Lives",
        "description": "Learn why hand hygiene is important for reducing the spread of germs and illness.",
        "video_url": "https://www.youtube.com/watch?v=BaHTZdJWYVw",
        "reward": 1000,
        "duration_seconds": 60,
        "category": "Health",
        "source": "CDC",
        "license": "Public Domain",
    },
    {
        "title": "Don't Get, Don't Spread Seasonal Flu",
        "description": "A short educational video about preventing and reducing the spread of seasonal flu.",
        "video_url": "https://www.youtube.com/watch?v=OPgP88Lct0Q",
        "reward": 1000,
        "duration_seconds": 60,
        "category": "Health",
        "source": "CDC",
        "license": "Public Domain",
    },
    {
        "title": "What You Need To Know About Handwashing",
        "description": "Important information about hand washing and the use of hand sanitizer.",
        "video_url": "https://commons.wikimedia.org/wiki/File:What_You_Need_To_Know_About_Handwashing.webm",
        "reward": 1000,
        "duration_seconds": 121,
        "category": "Health",
        "source": "CDC / Wikimedia Commons",
        "license": "Public Domain",
    },
    {
        "title": "Clean Hands Short",
        "description": "A very short demonstration showing hand washing to help prevent the spread of disease.",
        "video_url": "https://commons.wikimedia.org/wiki/File:Clean_hands_short.webm",
        "reward": 1000,
        "duration_seconds": 23,
        "category": "Health",
        "source": "CDC / Wikimedia Commons",
        "license": "Public Domain",
    },
    {
        "title": "Always Wash Your Hands Before, During and After Preparing Food",
        "description": "Learn why hand hygiene is important when preparing food.",
        "video_url": "https://commons.wikimedia.org/wiki/File:Always_wash_your_hands_before,_during,_and_after_preparing_food.webm",
        "reward": 1000,
        "duration_seconds": 60,
        "category": "Food Safety",
        "source": "CDC / Wikimedia Commons",
        "license": "Public Domain",
    },
]


def main():
    conn = sqlite3.connect(DATABASE)

    try:
        cursor = conn.cursor()

        print()
        print("=" * 50)
        print(" KORACASH REAL VIDEO LIBRARY")
        print("=" * 50)

        inserted = 0
        existing = 0

        for video in VIDEOS:

            found = cursor.execute(
                """
                SELECT id
                FROM videos
                WHERE title = ?
                """,
                (video["title"],)
            ).fetchone()

            if found:
                existing += 1

                cursor.execute(
                    """
                    UPDATE videos
                    SET
                        description = ?,
                        video_url = ?,
                        reward = ?,
                        duration_seconds = ?,
                        category = ?,
                        source = ?,
                        license = ?,
                        is_active = 1
                    WHERE id = ?
                    """,
                    (
                        video["description"],
                        video["video_url"],
                        video["reward"],
                        video["duration_seconds"],
                        video["category"],
                        video["source"],
                        video["license"],
                        found[0],
                    )
                )

                print("Updated:", video["title"])

            else:

                cursor.execute(
                    """
                    INSERT INTO videos
                    (
                        title,
                        description,
                        video_url,
                        reward,
                        is_active,
                        created_at,
                        duration_seconds,
                        category,
                        source,
                        license
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        video["title"],
                        video["description"],
                        video["video_url"],
                        video["reward"],
                        1,
                        datetime.now().isoformat(),
                        video["duration_seconds"],
                        video["category"],
                        video["source"],
                        video["license"],
                    )
                )

                inserted += 1
                print("Inserted:", video["title"])

        conn.commit()

        total = cursor.execute(
            "SELECT COUNT(*) FROM videos"
        ).fetchone()[0]

        active = cursor.execute(
            "SELECT COUNT(*) FROM videos WHERE is_active = 1"
        ).fetchone()[0]

        print()
        print("=" * 50)
        print("NEW VIDEOS INSERTED :", inserted)
        print("ALREADY EXISTING    :", existing)
        print("TOTAL VIDEOS        :", total)
        print("ACTIVE VIDEOS       :", active)
        print("=" * 50)
        print("VIDEO LIBRARY READY")
        print("=" * 50)
        print()

    except Exception as e:
        conn.rollback()
        print()
        print("ERROR:", e)
        print()

    finally:
        conn.close()


if __name__ == "__main__":
    main()