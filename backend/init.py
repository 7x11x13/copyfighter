from extensions import query


def init():
    with open("init.sql") as f:
        sql = f.read()

    query_results = query(sql)
    print(query_results)


if __name__ == "__main__":
    init()
