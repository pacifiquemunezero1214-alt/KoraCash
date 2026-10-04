import sqlite3
from datetime import datetime, timezone

DB_NAME = "koracash.db"
TASK_REWARD = 1000


def now_iso():
    return datetime.now(timezone.utc).isoformat()


TASKS = [
    # =========================
    # MATHEMATICS
    # =========================
    (
        "Mathematics",
        "Ushobora kubona angahe usigaranye?",
        "Ufite 10,000 Frw ukoresheje 3,500 Frw. Hasigaye angahe?",
        "5,500 Frw",
        "6,500 Frw",
        "7,500 Frw",
        "8,500 Frw",
        "B",
    ),
    (
        "Mathematics",
        "Percentage",
        "20% ya 10,000 Frw ni angahe?",
        "1,000 Frw",
        "2,000 Frw",
        "3,000 Frw",
        "4,000 Frw",
        "B",
    ),
    (
        "Mathematics",
        "Addition",
        "1,500 + 2,500 bingana iki?",
        "3,000",
        "4,000",
        "5,000",
        "6,000",
        "B",
    ),
    (
        "Mathematics",
        "Subtraction",
        "8,000 - 2,750 bingana iki?",
        "4,250",
        "5,250",
        "6,250",
        "7,250",
        "B",
    ),
    (
        "Mathematics",
        "Multiplication",
        "25 × 4 bingana iki?",
        "50",
        "75",
        "100",
        "125",
        "C",
    ),
    (
        "Mathematics",
        "Division",
        "12,000 Frw ugabanyije abantu 4 bingana angahe kuri buri muntu?",
        "2,000 Frw",
        "3,000 Frw",
        "4,000 Frw",
        "5,000 Frw",
        "B",
    ),
    (
        "Mathematics",
        "Percentage",
        "10% ya 50,000 Frw ni angahe?",
        "5,000 Frw",
        "10,000 Frw",
        "15,000 Frw",
        "20,000 Frw",
        "A",
    ),
    (
        "Mathematics",
        "Comparison",
        "Ni ikihe giciro kinini?",
        "4,500 Frw",
        "5,000 Frw",
        "4,750 Frw",
        "4,250 Frw",
        "B",
    ),

    # =========================
    # FINANCE
    # =========================
    (
        "Finance",
        "Saving",
        "Ni iki gifasha umuntu kugera ku ntego yo kwizigamira?",
        "Gukoresha amafaranga yose",
        "Kugena amafaranga yo kuzigama buri gihe",
        "Kugura ibintu byose abonye",
        "Kudakora budget",
        "B",
    ),
    (
        "Finance",
        "Budget",
        "Budget ni iki?",
        "Urutonde rw'amafaranga winjiza n'ayo uteganya gukoresha",
        "Inguzanyo gusa",
        "Amafaranga ari kuri telefone",
        "Umushahara gusa",
        "A",
    ),
    (
        "Finance",
        "Emergency Fund",
        "Emergency fund ikoreshwa cyane cyane mu ki?",
        "Kugura ibintu bidakenewe",
        "Ibibazo cyangwa amafaranga atateganyijwe",
        "Kwishimisha gusa",
        "Kugura internet gusa",
        "B",
    ),
    (
        "Finance",
        "Debt",
        "Mbere yo gufata inguzanyo, ni iki gikwiye kubanza kurebwa?",
        "Ubushobozi bwo kuyishyura",
        "Ibara ry'amafaranga",
        "Umubare w'inshuti",
        "Ubwoko bwa telefone",
        "A",
    ),
    (
        "Finance",
        "Profit",
        "Profit ni iki mu bucuruzi?",
        "Amafaranga yose wakoresheje",
        "Amafaranga winjije gusa",
        "Amafaranga asigara nyuma yo gukuramo ibiciro",
        "Umubare w'abakiriya",
        "C",
    ),
    (
        "Finance",
        "Cash Flow",
        "Cash flow ijyanye cyane n'iki?",
        "Uko amafaranga yinjira n'asohoka",
        "Umubare w'abakozi gusa",
        "Izina ry'ubucuruzi",
        "Igihe cyo gufungura shop",
        "A",
    ),

    # =========================
    # BUSINESS
    # =========================
    (
        "Business",
        "Customer Service",
        "Ni iki gifasha business kugumana abakiriya?",
        "Kubasuzugura",
        "Serivisi nziza",
        "Kubaka ibiciro bidafite gahunda",
        "Kutabumva",
        "B",
    ),
    (
        "Business",
        "Stock",
        "Kuki kubara stock ari ingenzi?",
        "Kumenya ibicuruzwa bihari",
        "Kongera ibiciro buri munsi",
        "Kwirukana abakiriya",
        "Kugabanya shop",
        "A",
    ),
    (
        "Business",
        "Sales",
        "Ni iki gishobora gufasha kongera sales?",
        "Kumva ibyo abakiriya bakeneye",
        "Kwirengagiza abakiriya",
        "Kutamenya ibicuruzwa",
        "Guhisha ibiciro byose",
        "A",
    ),
    (
        "Business",
        "Record Keeping",
        "Kuki business ikwiye kubika records?",
        "Kugira ngo ikurikirane amafaranga n'ibikorwa",
        "Kugira ngo itamenya profit",
        "Kugira ngo itagira budget",
        "Kugira ngo itagira abakiriya",
        "A",
    ),
    (
        "Business",
        "Pricing",
        "Ni iki gikwiye kwitabwaho mu gushyiraho igiciro?",
        "Cost n'inyungu wifuza",
        "Ibara ry'igicuruzwa gusa",
        "Umubare wa telefone",
        "Izina ry'umukozi",
        "A",
    ),

    # =========================
    # HEALTH
    # =========================
    (
        "Health",
        "Hygiene",
        "Ni ikihe gikorwa gifasha kwirinda indwara nyinshi?",
        "Gukaraba intoki neza",
        "Kudasukura",
        "Kudasinzira",
        "Kutanywa amazi",
        "A",
    ),
    (
        "Health",
        "Nutrition",
        "Indyo yuzuye iba ikubiyemo iki?",
        "Ubwoko bumwe bw'ibiryo gusa",
        "Ibice bitandukanye by'ibiribwa bikenewe n'umubiri",
        "Isukari gusa",
        "Amazi gusa",
        "B",
    ),
    (
        "Health",
        "Water",
        "Kunywa amazi bifasha iki?",
        "Gufasha umubiri gukora neza",
        "Guhagarika burundu igogora",
        "Kwangiza umubiri buri gihe",
        "Gukuraho ibitotsi burundu",
        "A",
    ),
    (
        "Health",
        "Exercise",
        "Imyitozo ngororamubiri isanzwe ishobora gufasha iki?",
        "Ubuzima rusange",
        "Kwangiza imitsi buri gihe",
        "Kudakoresha umubiri",
        "Kongera indwara zose",
        "A",
    ),

    # =========================
    # TECHNOLOGY
    # =========================
    (
        "Technology",
        "Password",
        "Password ikomeye iba imeze ite?",
        "123456",
        "Izina gusa",
        "Ivanga inyuguti, imibare n'ibimenyetso",
        "Phone number gusa",
        "C",
    ),
    (
        "Technology",
        "Cyber Safety",
        "Ni iki udakwiye gusangiza umuntu utizeye?",
        "Password yawe",
        "Izina rya app",
        "Igihe",
        "Language",
        "A",
    ),
    (
        "Technology",
        "Phishing",
        "Phishing ikunze kugerageza gukora iki?",
        "Kwiba amakuru y'umukoresha",
        "Gusukura computer",
        "Kongera battery",
        "Kongera internet speed",
        "A",
    ),
    (
        "Technology",
        "Backup",
        "Backup ifasha iki?",
        "Kubika kopi y'amakuru kugira ngo adatakara",
        "Gusiba files zose",
        "Kwangiza database",
        "Guhagarika computer",
        "A",
    ),
    (
        "Technology",
        "Internet",
        "Ni iki internet ikoreshwa cyane?",
        "Guhuza no gusangira amakuru",
        "Guhagarika communication",
        "Gusiba telefoni",
        "Guhindura battery",
        "A",
    ),

    # =========================
    # SAFETY
    # =========================
    (
        "Safety",
        "Road Safety",
        "Iyo wambuka umuhanda, ni iki gikwiye kubanza gukorwa?",
        "Kureba neza impande zombi",
        "Gukoresha telefone",
        "Kwiruka utarebye",
        "Gufunga amaso",
        "A",
    ),
    (
        "Safety",
        "Fire Safety",
        "Iyo habaye inkongi y'umuriro, ni iki gikwiye kwitabwaho mbere?",
        "Umutekano w'abantu",
        "Kufata ibintu byose",
        "Gufotora gusa",
        "Gukomeza akazi",
        "A",
    ),
    (
        "Safety",
        "Electricity",
        "Iyo insinga y'amashanyarazi yangiritse, ukwiye gukora iki?",
        "Kuyikoraho",
        "Kuyisiga amazi",
        "Kuyirinda no gushaka ubufasha bukwiye",
        "Kuyikoresha cyane",
        "C",
    ),

    # =========================
    # GENERAL KNOWLEDGE
    # =========================
    (
        "General Knowledge",
        "Geography",
        "Umurwa mukuru w'u Rwanda ni uwuhe?",
        "Kigali",
        "Huye",
        "Musanze",
        "Rubavu",
        "A",
    ),
    (
        "General Knowledge",
        "Language",
        "Ni uruhe rurimi rukoreshwa cyane mu Rwanda nk'ururimi rw'igihugu?",
        "Kinyarwanda",
        "Igitaliyani",
        "Igiporutugali",
        "Igishinwa",
        "A",
    ),
    (
        "General Knowledge",
        "Time",
        "Umunsi umwe ugira amasaha angahe?",
        "12",
        "18",
        "24",
        "48",
        "C",
    ),
    (
        "General Knowledge",
        "Science",
        "Amazi afitwe mu buryo busanzwe afite iyihe formula?",
        "CO2",
        "H2O",
        "O2",
        "NaCl",
        "B",
    ),

    # =========================
    # PROBLEM SOLVING
    # =========================
    (
        "Problem Solving",
        "Decision Making",
        "Iyo ufite ikibazo, intambwe ya mbere nziza ni iyihe?",
        "Kukirengagiza",
        "Kumva ikibazo neza",
        "Gushinja abandi",
        "Gufata umwanzuro utabanje kureba amakuru",
        "B",
    ),
    (
        "Problem Solving",
        "Planning",
        "Kuki gutegura gahunda ari ingenzi?",
        "Bifasha gukoresha igihe neza",
        "Bituma igihe kibura",
        "Bituma nta ntego iba",
        "Bituma ibintu byose bihagarara",
        "A",
    ),
    (
        "Problem Solving",
        "Critical Thinking",
        "Mbere yo kwizera amakuru yo kuri internet, ni iki cyiza gukora?",
        "Kuyasangira ako kanya",
        "Kugenzura source yayo",
        "Kuyasiba",
        "Kuyahindura",
        "B",
    ),

    # =========================
    # COMMUNICATION
    # =========================
    (
        "Communication",
        "Listening",
        "Kumva neza umuntu uvugana nawe bisaba iki?",
        "Kumutega amatwi",
        "Kumuca mu ijambo buri gihe",
        "Kureba telefone gusa",
        "Kumwirengagiza",
        "A",
    ),
    (
        "Communication",
        "Respect",
        "Ni iki gifasha communication kuba nziza?",
        "Kubaha uwo muvugana",
        "Kumubwira nabi",
        "Kumuca mu ijambo",
        "Kumwirengagiza",
        "A",
    ),
    (
        "Communication",
        "Clarity",
        "Iyo utanga message, kuki ari byiza gukoresha amagambo asobanutse?",
        "Kugira ngo ubutumwa bwumvikane",
        "Kugira ngo burusheho kuyobera",
        "Kugira ngo abantu batabumenya",
        "Kugira ngo butagira icyo busobanura",
        "A",
    ),

    # =========================
    # DAILY LIFE
    # =========================
    (
        "Daily Life",
        "Time Management",
        "Ni iki gifasha gucunga igihe neza?",
        "Gushyiraho priorities",
        "Gukora ibintu nta gahunda",
        "Gusubika byose",
        "Kutagira gahunda",
        "A",
    ),
    (
        "Daily Life",
        "Cleanliness",
        "Kuki isuku ari ingenzi mu buzima bwa buri munsi?",
        "Ifasha kubungabunga ubuzima n'aho dutuye",
        "Ituma indwara ziyongera buri gihe",
        "Ituma ibiryo byangirika",
        "Nta cyo imaze",
        "A",
    ),
    (
        "Daily Life",
        "Planning",
        "Iyo ufite ibintu byinshi byo gukora, ni iki cyiza?",
        "Kubishyira ku rutonde ukurikije priority",
        "Kubireka byose",
        "Gukora icyo ubonye gusa",
        "Kutagira gahunda",
        "A",
    ),
]


def main():
    conn = sqlite3.connect(DB_NAME)

    try:
        inserted = 0
        skipped = 0

        for (
            category,
            title,
            description,
            option_a,
            option_b,
            option_c,
            option_d,
            correct_answer,
        ) in TASKS:

            existing = conn.execute(
                """
                SELECT id
                FROM tasks
                WHERE title = ?
                  AND description = ?
                LIMIT 1
                """,
                (title, description),
            ).fetchone()

            if existing:
                skipped += 1
                continue

            conn.execute(
                """
                INSERT INTO tasks (
                    title,
                    description,
                    reward,
                    is_active,
                    created_at,
                    category,
                    option_a,
                    option_b,
                    option_c,
                    option_d,
                    correct_answer
                )
                VALUES (?, ?, ?, 1, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    title,
                    description,
                    TASK_REWARD,
                    now_iso(),
                    category,
                    option_a,
                    option_b,
                    option_c,
                    option_d,
                    correct_answer,
                ),
            )

            inserted += 1

        conn.commit()

        total = conn.execute(
            "SELECT COUNT(*) FROM tasks"
        ).fetchone()[0]

        active = conn.execute(
            "SELECT COUNT(*) FROM tasks WHERE is_active = 1"
        ).fetchone()[0]

        print()
        print("======================================")
        print(" KORACASH TASK LIBRARY")
        print("======================================")
        print(f"New tasks inserted : {inserted}")
        print(f"Already existing   : {skipped}")
        print(f"Total tasks        : {total}")
        print(f"Active tasks       : {active}")
        print("======================================")
        print("TASK LIBRARY READY")
        print("======================================")

    except Exception as e:
        conn.rollback()
        print()
        print("ERROR:", e)

    finally:
        conn.close()


if __name__ == "__main__":
    main()