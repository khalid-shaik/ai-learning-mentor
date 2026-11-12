"""Built-in course packs. Every code sample, SQL solution and numeric quiz answer is verified by the test suite."""


def Q(q, options, answer, why, code=None, run=False, verify=None):
    return {"q": q, "code": code, "options": options, "answer": answer, "why": why, "run": run, "verify": verify}


def L(lid, title, minutes, body, example, lang, points, quiz, cards, exercises=()):
    for n, q in enumerate(quiz, 1):
        q["id"] = f"{lid}-q{n}"
    return {"id": lid, "title": title, "minutes": minutes, "body": body.strip(), "example": example.strip(), "lang": lang, "points": points,
            "quiz": quiz, "cards": cards, "exercises": [{**e, "id": f"{lid}-e{i}"} for i, e in enumerate(exercises, 1)]}


SQL_SCHEMA = """customers(id, name, city, signup_date)   -- 8 customers
orders(id, customer_id, order_date, amount, status)   -- 12 orders, status: paid / pending / refunded"""

SQL = {"id": "sql", "title": "SQL Fundamentals", "level": "Beginner", "desc": "Query real data with SELECT, GROUP BY, JOINs and window functions. Practise in a live sandbox.",
       "lessons": [
    L("sql-1", "Reading data: SELECT, WHERE, ORDER BY", 10, """
A **table** stores rows (records) and columns (fields). `SELECT` chooses which columns you see and `FROM` names the table.

`WHERE` filters **individual rows** before they are returned. You can combine conditions with `AND` / `OR`, test lists with `IN (...)` and match patterns with `LIKE` (`%` means "any characters"). Text values go in single quotes.

`ORDER BY` sorts the result (ascending by default, `DESC` for descending) and `LIMIT n` keeps only the first n rows. Together, `ORDER BY amount DESC LIMIT 3` gives the three largest amounts.

`NULL` means "unknown". Compare it with `IS NULL`, never with `= NULL`.
""", """SELECT name, city
FROM customers
WHERE city = 'Hyderabad'
ORDER BY name;""", "sql",
      [("SELECT chooses columns and FROM names the table", ["select", "from", "column"]),
       ("WHERE filters individual rows before they are returned", ["where", "filter", "row"]),
       ("ORDER BY sorts and LIMIT keeps the first n rows", ["order by", "sort", "limit", "desc"])],
      [Q("Which clause filters individual rows?", ["WHERE", "HAVING", "ORDER BY", "LIMIT"], 0, "WHERE filters rows. HAVING filters groups after aggregation."),
       Q("What does ORDER BY amount DESC LIMIT 3 return?", ["The 3 smallest amounts", "The 3 largest amounts", "Any 3 rows", "The first 3 rows by id"], 1, "DESC sorts largest first and LIMIT 3 keeps the top three."),
       Q("Which condition finds names that start with 'A'?", ["name = 'A'", "name LIKE 'A%'", "name IN 'A'", "name STARTS 'A'"], 1, "LIKE with % matches any characters after the A.")],
      [("What does WHERE do?", "Filters rows before they are returned"), ("How do you sort from largest to smallest?", "ORDER BY column DESC"),
       ("How do you keep only the first n rows?", "LIMIT n"), ("Which wildcard matches any characters in LIKE?", "% (percent sign)"), ("How do you test for missing values?", "IS NULL (never = NULL)")],
      [{"prompt": "List the names of customers in Delhi, sorted alphabetically.", "solution": "SELECT name FROM customers WHERE city = 'Delhi' ORDER BY name",
        "ordered": True, "hint": "Filter with WHERE city = 'Delhi', then ORDER BY name."},
       {"prompt": "Show the id and amount of the 3 largest paid orders, biggest first.", "solution": "SELECT id, amount FROM orders WHERE status = 'paid' ORDER BY amount DESC LIMIT 3",
        "ordered": True, "hint": "WHERE status = 'paid', ORDER BY amount DESC, LIMIT 3."}]),
    L("sql-2", "Summarising: aggregates and GROUP BY", 12, """
**Aggregate functions** collapse many rows into one value: `COUNT`, `SUM`, `AVG`, `MIN`, `MAX`. `COUNT(*)` counts rows.

`GROUP BY` splits rows into groups and computes the aggregate for each group. Every selected column must either be in the `GROUP BY` or be inside an aggregate.

`WHERE` filters rows **before** grouping. `HAVING` filters groups **after** aggregation, so it can use aggregates like `HAVING COUNT(*) >= 2`.

Give results readable names with `AS`, for example `SUM(amount) AS total`.
""", """SELECT city, COUNT(*) AS customers
FROM customers
GROUP BY city
HAVING COUNT(*) >= 2
ORDER BY customers DESC;""", "sql",
      [("Aggregate functions such as COUNT, SUM and AVG summarise many rows into one value", ["aggregate", "count", "sum", "avg", "summar"]),
       ("GROUP BY splits rows into groups and aggregates each group", ["group by", "group"]),
       ("WHERE filters rows before grouping while HAVING filters groups after aggregation", ["where", "having", "after", "before"])],
      [Q("Which clause filters groups after aggregation?", ["WHERE", "HAVING", "LIMIT", "DISTINCT"], 1, "HAVING works on aggregated results; WHERE works on raw rows."),
       Q("What does COUNT(*) count?", ["Distinct values", "Non-null values in one column", "All rows in the group", "Columns"], 2, "COUNT(*) counts rows, including those with NULLs."),
       Q("What is wrong with: SELECT city, name FROM customers GROUP BY city?", ["Nothing", "name is neither grouped nor aggregated", "GROUP BY needs HAVING", "city cannot be grouped"], 1, "Each selected column must be grouped or aggregated; several names exist per city.")],
      [("What does GROUP BY do?", "Splits rows into groups so aggregates are computed per group"), ("WHERE vs HAVING?", "WHERE filters rows before grouping; HAVING filters groups after aggregation"),
       ("What does COUNT(*) return?", "The number of rows"), ("How do you rename a result column?", "Use AS, e.g. SUM(amount) AS total")],
      [{"prompt": "How many paid orders are there and what is their total amount?", "solution": "SELECT COUNT(*), SUM(amount) FROM orders WHERE status = 'paid'", "ordered": False,
        "hint": "COUNT(*) and SUM(amount) with WHERE status = 'paid'."},
       {"prompt": "Show each customer_id with their total paid amount, only for totals above 1000.",
        "solution": "SELECT customer_id, SUM(amount) FROM orders WHERE status = 'paid' GROUP BY customer_id HAVING SUM(amount) > 1000", "ordered": False,
        "hint": "WHERE for paid rows, GROUP BY customer_id, HAVING SUM(amount) > 1000."}]),
    L("sql-3", "Combining tables: JOINs", 12, """
Data is split across tables to avoid repetition. A **primary key** uniquely identifies a row (`customers.id`) and a **foreign key** points to it from another table (`orders.customer_id`).

`JOIN` (an inner join) keeps only rows that match on both sides. `LEFT JOIN` keeps **all** rows from the left table and fills `NULL` where there is no match, which is how you find "customers with no orders".

Use short **aliases** (`customers c`) and qualify columns (`c.name`) so it is clear where each column comes from. The join condition goes in `ON`.
""", """SELECT c.name, o.amount
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE o.status = 'paid';""", "sql",
      [("A foreign key in one table points to the primary key of another", ["foreign key", "primary key"]),
       ("An inner JOIN keeps only rows that match in both tables", ["inner", "join", "match"]),
       ("LEFT JOIN keeps every row from the left table and uses NULL where nothing matches", ["left join", "left", "null"])],
      [Q("What does LEFT JOIN keep?", ["Only matching rows", "All rows from the left table, even without a match", "All rows from both tables", "Only unmatched rows"], 1, "Left rows are always kept; unmatched right columns become NULL."),
       Q("What does a join condition usually link?", ["Two aggregates", "A primary key to a foreign key", "Two ORDER BY clauses", "Two databases"], 1, "ON compares the key in one table to the matching key in the other."),
       Q("Customer Hari has no orders. Which query returns Hari with NULL amount?", ["customers JOIN orders", "customers LEFT JOIN orders", "orders JOIN customers", "customers WHERE orders IS NULL"], 1, "Only LEFT JOIN from customers keeps customers without orders.")],
      [("What is a primary key?", "A column that uniquely identifies each row"), ("What is a foreign key?", "A column that refers to the primary key of another table"),
       ("How do you find rows with no match in another table?", "LEFT JOIN and filter WHERE right_table.id IS NULL"), ("Where does the join condition go?", "In the ON clause")],
      [{"prompt": "List each customer's name and number of orders, including customers with zero orders.",
        "solution": "SELECT c.name, COUNT(o.id) FROM customers c LEFT JOIN orders o ON o.customer_id = c.id GROUP BY c.id", "ordered": False,
        "hint": "LEFT JOIN from customers, then COUNT(o.id) (not COUNT(*)) so zero-order customers show 0."},
       {"prompt": "Show the names of customers who have never placed an order.",
        "solution": "SELECT c.name FROM customers c LEFT JOIN orders o ON o.customer_id = c.id WHERE o.id IS NULL", "ordered": False,
        "hint": "LEFT JOIN, then keep rows where the order id IS NULL."}]),
    L("sql-4", "Going further: subqueries, CTEs and window functions", 15, """
A **subquery** is a query inside another query. A **CTE** (`WITH name AS (...)`) gives a subquery a name so the main query reads top to bottom.

**Window functions** calculate across related rows **without collapsing them**. `PARTITION BY` splits rows into groups for the calculation, `ORDER BY` inside `OVER` sets the order. Common ones: `ROW_NUMBER()`, `RANK()` and `SUM(...) OVER (ORDER BY ...)` for running totals.

"Top row per group" is a classic pattern: number the rows with `ROW_NUMBER() OVER (PARTITION BY group ORDER BY value DESC)` inside a CTE, then keep `rn = 1`.
""", """SELECT order_date, amount,
       SUM(amount) OVER (ORDER BY order_date) AS running_total
FROM orders
WHERE status = 'paid';""", "sql",
      [("A CTE names a subquery with WITH so the query is easier to read", ["cte", "with", "subquery", "named"]),
       ("Window functions calculate across rows without collapsing them into one row", ["window", "over", "without", "collapse"]),
       ("PARTITION BY splits the rows into groups for a window calculation", ["partition"])],
      [Q("What does PARTITION BY do in a window function?", ["Removes duplicates", "Splits rows into groups for the calculation without collapsing them", "Sorts the final result", "Joins two tables"], 1, "Unlike GROUP BY, every row stays in the output."),
       Q("Best tool for 'the top order per customer'?", ["COUNT(*)", "ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC)", "LIMIT 1", "HAVING MAX"], 1, "Number rows within each customer, then keep number 1."),
       Q("What is a CTE?", ["A table stored permanently", "A named temporary result defined with WITH", "A kind of join", "An index"], 1, "It exists only for the duration of the query.")],
      [("What is a CTE?", "A named temporary result set defined with WITH"), ("What does a window function do?", "Calculates across related rows while keeping every row"),
       ("How do you build a running total?", "SUM(col) OVER (ORDER BY ...)"), ("Pattern for top row per group?", "ROW_NUMBER() OVER (PARTITION BY g ORDER BY v DESC) then keep rn = 1")],
      [{"prompt": "Show each paid order's id and amount with a running total of paid amounts, ordered by order_date.",
        "solution": "SELECT id, amount, SUM(amount) OVER (ORDER BY order_date, id) FROM orders WHERE status = 'paid' ORDER BY order_date, id", "ordered": True,
        "hint": "SUM(amount) OVER (ORDER BY order_date), and ORDER BY order_date at the end."},
       {"prompt": "Return each customer's single largest paid order (customer_id and amount).",
        "solution": "WITH r AS (SELECT customer_id, amount, ROW_NUMBER() OVER (PARTITION BY customer_id ORDER BY amount DESC) AS rn FROM orders WHERE status = 'paid') SELECT customer_id, amount FROM r WHERE rn = 1",
        "ordered": False, "hint": "MAX(amount) with GROUP BY works too, or ROW_NUMBER in a CTE."}]),
]}

PY = {"id": "py", "title": "Python for Data", "level": "Beginner", "desc": "Core Python you need before pandas: types, collections, functions and files.",
      "lessons": [
    L("py-1", "Values, types and strings", 10, """
Everything in Python is a **value with a type**: `int` (whole numbers), `float` (decimals), `str` (text) and `bool` (`True` / `False`). Use `type(x)` to check.

Arithmetic: `/` always gives a float, `//` is **floor division** (rounds down) and `%` gives the **remainder**.

**f-strings** put values inside text: `f"{name} scored {score:.1f}%"`. The `:.1f` part formats a float with one decimal. Strings also have methods such as `.upper()`, `.strip()`, `.split()` and `.replace()`.
""", """name = "Asha"
score = 92.5
print(f"{name} scored {score:.1f}%")
print(type(score))
print(7 // 2, 7 % 2)""", "python",
      [("Core types are int, float, str and bool", ["int", "float", "str", "bool", "type"]),
       ("// does floor division and % returns the remainder", ["floor", "//", "remainder", "%"]),
       ("f-strings insert values into text and can format numbers", ["f-string", "format", "insert"])],
      [Q("What does this print?", ["3.5 1", "3 1", "4 1", "3 0"], 1, "7 // 2 is 3 (rounded down) and 7 % 2 is 1.", code='print(7 // 2, 7 % 2)', run=True),
       Q("What does this print?", ["Data!!", "DATA!!", "DATA!", "data!!"], 1, "upper() makes DATA, then '!' * 2 repeats the exclamation mark.", code='print("data".upper() + "!" * 2)', run=True),
       Q("Best way to put a variable inside a string?", ["Concatenate with + and str()", "An f-string like f\"{x}\"", "The % operator only", "You cannot"], 1, "f-strings are readable and support formatting.")],
      [("What does // do?", "Floor division: divides and rounds down"), ("What does % return?", "The remainder of a division"),
       ("How do you format 2 decimals in an f-string?", "f\"{x:.2f}\""), ("What does type(x) return?", "The data type of x")]),
    L("py-2", "Lists, dictionaries and loops", 12, """
A **list** is an ordered, changeable sequence: `nums = [1, 2, 3]`. Index from 0 (`nums[0]`) and slice with `nums[1:3]` (start included, end excluded).

A **dictionary** maps **keys to values**: `scores = {"Asha": 92}`. Read with `scores["Asha"]`, add with `scores["Ben"] = 78`, loop with `.items()`.

A **for loop** repeats work for each item. Remember: `len(x)` gives the size, and `sum(x)` adds numbers.
""", """scores = {"Asha": 92, "Ben": 78, "Chitra": 85}
total = 0
for name, s in scores.items():
    total += s
print(total / len(scores))""", "python",
      [("Lists are ordered and indexed from 0; slices exclude the end index", ["list", "index", "slice", "0"]),
       ("Dictionaries map keys to values", ["dictionary", "dict", "key", "value"]),
       ("A for loop repeats work for each item in a collection", ["for", "loop", "each", "item"])],
      [Q("What does this print?", ["[1, 2]", "[2, 3]", "[2, 3, 4]", "[1, 2, 3]"], 1, "A slice [1:3] starts at index 1 and stops before index 3.", code="nums = [1, 2, 3, 4]\nprint(nums[1:3])", run=True),
       Q("What does this print?", ["1", "2", "3", "Error"], 1, "The dictionary ends with two keys, a and b.", code='d = {"a": 1}\nd["b"] = 2\nprint(len(d))', run=True),
       Q("Which structure maps keys to values?", ["list", "tuple", "dict", "set"], 2, "A dict looks values up by key.")],
      [("What index does the first list item have?", "0"), ("Does the slice nums[1:3] include index 3?", "No, the end index is excluded"),
       ("How do you loop over keys and values of a dict?", "for k, v in d.items():"), ("How do you add or change a dict entry?", "d[key] = value")]),
    L("py-3", "Functions and comprehensions", 12, """
A **function** packages reusable logic: `def average(values): return sum(values) / len(values)`. Inputs are **parameters**; `return` sends a result back. A function without `return` gives back `None`.

A **list comprehension** builds a list in one line: `[x**2 for x in range(5) if x % 2 == 0]`. Read it as "x squared, for each x in range(5), if x is even".

Small, well-named functions make data code easier to test and reuse.
""", """def average(values):
    return sum(values) / len(values)

squares = [x**2 for x in range(5) if x % 2 == 0]
print(average([2, 4, 6]), squares)""", "python",
      [("A function packages reusable logic and returns a value with return", ["function", "def", "return", "reusable"]),
       ("A function without return gives back None", ["none", "return"]),
       ("A list comprehension builds a list in one line with an optional condition", ["comprehension", "list", "condition", "one line"])],
      [Q("What does this print?", ["[0, 2, 4, 6]", "[0, 1, 2, 3]", "[2, 4, 6, 8]", "[0, 2, 4]"], 0, "range(4) gives 0 to 3 and each is doubled.", code="print([x * 2 for x in range(4)])", run=True),
       Q("What does a function with no return statement give back?", ["0", "An empty string", "None", "An error"], 2, "Python returns None when no return is executed."),
       Q("What does this print?", ["2", "3", "4", "Error"], 1, "f(1) is 2, then f(2) is 3.", code="def f(x):\n    return x + 1\nprint(f(f(1)))", run=True)],
      [("How do you define a function?", "def name(parameters): ... return value"), ("What does a function return if it has no return?", "None"),
       ("Write the squares of 0-4 as a comprehension", "[x**2 for x in range(5)]"), ("What is a parameter?", "A named input of a function")]),
    L("py-4", "Working with files and data", 12, """
Real data lives in files. The standard `csv` module reads them: `csv.DictReader` turns each row into a **dictionary keyed by the header names**.

Use `with open(path) as f:` so the file is **closed automatically**, even if an error happens.

`collections.Counter` counts items and `Counter.most_common(n)` returns the n most frequent. Combine these tools to summarise a file before moving to pandas.
""", """import csv, io
from collections import Counter

data = io.StringIO("city,sales\\nHyd,10\\nMum,20\\nHyd,5\\n")
totals = Counter()
for row in csv.DictReader(data):
    totals[row["city"]] += int(row["sales"])
print(dict(totals))""", "python",
      [("csv.DictReader gives each row as a dictionary keyed by the header names", ["dictreader", "dictionary", "header", "csv"]),
       ("with open(...) closes the file automatically", ["with", "open", "close"]),
       ("Counter counts items and most_common returns the most frequent", ["counter", "most_common", "count"])],
      [Q("What does this print?", ["[('a', 3)]", "[('b', 1)]", "[('n', 2)]", "a"], 0, "'a' appears three times in 'banana'.", code='from collections import Counter\nprint(Counter("banana").most_common(1))', run=True),
       Q("Why use `with open(...) as f`?", ["It makes reading faster", "It closes the file automatically", "It converts text to numbers", "It is required for csv"], 1, "The file is closed even if an error occurs."),
       Q("csv.DictReader gives each row as...", ["A list of numbers", "A dictionary keyed by header names", "A single string", "A pandas DataFrame"], 1, "Column headers become the dictionary keys.")],
      [("Why use a with block for files?", "It closes the file automatically"), ("What does csv.DictReader return per row?", "A dictionary keyed by the header names"),
       ("What does Counter.most_common(1) return?", "A list with the most frequent item and its count"), ("What does int('5') do?", "Converts the string '5' to the integer 5")]),
]}

STATS = {"id": "stats", "title": "Statistics Essentials", "level": "Beginner", "desc": "The statistics every analyst needs: spread, probability, sampling and hypothesis tests.",
         "lessons": [
    L("st-1", "Centre and spread", 10, """
The **mean** is the average, the **median** is the middle value when sorted and the **mode** is the most frequent value. The mean is pulled by outliers; the **median is robust** to them.

**Spread** tells you how far values vary: the **range** (max minus min), the **variance** and the **standard deviation** (the typical distance from the mean, in the same units as the data).

Always report centre **and** spread: two datasets can share a mean and still look very different.
""", """import statistics as st
data = [2, 4, 4, 4, 5, 5, 7, 9]
print(st.mean(data), st.median(data), st.mode(data), st.pstdev(data))""", "python",
      [("Mean, median and mode describe the centre of the data", ["mean", "median", "mode", "centre", "center"]),
       ("The median is robust to outliers while the mean is not", ["median", "outlier", "robust"]),
       ("Standard deviation measures typical distance from the mean", ["standard deviation", "spread", "variance", "distance"])],
      [Q("What is the mean of 2, 4, 4, 4, 5, 5, 7, 9?", ["4.5", "5", "4", "5.5"], 1, "The sum is 40 and there are 8 values.", verify=("statistics.mean([2,4,4,4,5,5,7,9])", "5")),
       Q("Which measure is least affected by outliers?", ["Mean", "Median", "Range", "Variance"], 1, "One huge value moves the mean a lot but barely changes the median."),
       Q("Salaries: 30k, 32k, 35k, 36k, 400k. Which best describes a typical salary?", ["Mean", "Median", "Maximum", "Range"], 1, "The 400k outlier inflates the mean; the median is 35k.")],
      [("What is the median?", "The middle value when the data is sorted"), ("Which is more robust to outliers: mean or median?", "The median"),
       ("What does standard deviation measure?", "The typical distance of values from the mean"), ("What is the range?", "Maximum minus minimum")]),
    L("st-2", "Probability and the normal distribution", 12, """
**Probability** is a number from 0 to 1. For equally likely outcomes it is favourable outcomes divided by total outcomes. For **independent** events, multiply: P(A and B) = P(A) x P(B).

The **normal distribution** is the symmetric bell curve. About **68%** of values fall within 1 standard deviation of the mean, **95%** within 2 and **99.7%** within 3.

A **z-score** says how many standard deviations a value is from the mean: `z = (x - mean) / sd`.
""", """x, mean, sd = 85, 70, 10
z = (x - mean) / sd
print(z)""", "python",
      [("Probability is between 0 and 1 and independent events multiply", ["probability", "independent", "multiply", "0 and 1"]),
       ("In a normal distribution about 68 percent of values lie within one standard deviation", ["68", "normal", "standard deviation"]),
       ("A z-score is the number of standard deviations from the mean", ["z-score", "z score", "standard deviations", "mean"])],
      [Q("A fair six-sided die is rolled. What is P(even)?", ["0.25", "0.5", "0.33", "0.67"], 1, "Three of six outcomes (2, 4, 6) are even.", verify=("3/6", "0.5")),
       Q("In a normal distribution, about what percentage lies within 1 standard deviation of the mean?", ["50%", "68%", "95%", "99.7%"], 1, "The 68-95-99.7 rule: 68% within 1 sd."),
       Q("What is the z-score of x = 85 when mean = 70 and sd = 10?", ["0.5", "1.5", "15", "8.5"], 1, "(85 - 70) / 10 = 1.5.", verify=("(85-70)/10", "1.5"))],
      [("Range of a probability?", "0 to 1"), ("P(A and B) for independent events?", "P(A) x P(B)"), ("What is the 68-95-99.7 rule?", "Share of normal data within 1, 2 and 3 standard deviations"),
       ("Formula for a z-score?", "z = (x - mean) / standard deviation")]),
    L("st-3", "Sampling and confidence intervals", 12, """
A **population** is everyone you care about; a **sample** is the part you actually measure. A sample must be **representative**, otherwise **sampling bias** misleads you however large it is.

The **standard error** of the mean is `s / sqrt(n)`: it **shrinks as the sample size grows**. A **95% confidence interval** is roughly `mean +/- 1.96 x standard error`.

Interpretation: if you repeated the sampling many times, about 95% of such intervals would contain the true mean. It does **not** say the true mean is in this one interval with 95% probability.
""", """mean, s, n = 50, 10, 100
se = s / n ** 0.5
print(se, mean - 1.96 * se, mean + 1.96 * se)""", "python",
      [("A sample should be representative or sampling bias misleads", ["sample", "representative", "bias", "population"]),
       ("Standard error is s divided by the square root of n and shrinks as n grows", ["standard error", "sqrt", "shrink", "larger sample", "n"]),
       ("A 95 percent confidence interval is about the mean plus or minus 1.96 standard errors", ["confidence interval", "1.96", "95"])],
      [Q("What happens to the standard error as the sample size n increases?", ["It increases", "It decreases", "It stays the same", "It becomes the mean"], 1, "SE = s / sqrt(n), so a larger n gives a smaller SE."),
       Q("What does a 95% confidence interval mean?", ["The mean is in this interval with 95% probability", "95% of the data lies in the interval", "About 95% of intervals built this way would contain the true mean", "The sample is 95% accurate"], 2, "It describes the long-run behaviour of the method."),
       Q("What is the standard error when s = 20 and n = 100?", ["0.2", "2", "20", "200"], 1, "20 / sqrt(100) = 2.", verify=("20/100**0.5", "2"))],
      [("Population vs sample?", "The whole group vs the part you measure"), ("Formula for the standard error of the mean?", "s / sqrt(n)"),
       ("Approximate 95% confidence interval?", "mean +/- 1.96 x standard error"), ("What is sampling bias?", "A sample that does not represent the population")]),
    L("st-4", "Hypothesis testing and A/B tests", 15, """
A **hypothesis test** asks whether data is surprising if nothing is going on. The **null hypothesis** (H0) says "no effect"; the **alternative** says there is one.

The **p-value** is the probability of seeing data **at least this extreme if the null hypothesis is true**. If p is below your **significance level** (usually 0.05) you reject H0.

A **Type I error** is rejecting a true null (a false positive); a **Type II error** is missing a real effect. **Statistically significant is not the same as practically important**: check the size of the effect too.

In an **A/B test** you compare two conversion rates. Example: 10% vs 12% with 1,000 users each gives p of about 0.15, so the difference is not significant at 5%.
""", """import math
p1, p2, n = 0.10, 0.12, 1000
pooled = (p1 + p2) / 2
se = math.sqrt(pooled * (1 - pooled) * (2 / n))
z = (p2 - p1) / se
p_value = math.erfc(abs(z) / math.sqrt(2))
print(round(z, 2), round(p_value, 2))""", "python",
      [("The null hypothesis says there is no effect and the p-value is computed assuming it is true", ["null", "no effect", "p-value", "assuming"]),
       ("If p is below the significance level such as 0.05 you reject the null", ["0.05", "significance", "reject"]),
       ("Type I is a false positive and statistical significance is not practical importance", ["type i", "false positive", "practical", "effect size"])],
      [Q("What is a p-value?", ["The probability the null hypothesis is true", "The probability of data at least this extreme if the null hypothesis is true", "The size of the effect", "The sample size"], 1, "It is computed assuming the null is true; it is not the probability the null is true."),
       Q("p = 0.03 and alpha = 0.05. What do you conclude?", ["Fail to reject the null", "Reject the null at the 5% level", "The effect is large", "The test is invalid"], 1, "0.03 < 0.05, so the result is statistically significant."),
       Q("What is a Type I error?", ["Missing a real effect", "Rejecting a true null hypothesis", "Using a small sample", "Computing the mean wrongly"], 1, "A false positive: you claim an effect that is not there.")],
      [("What is the null hypothesis?", "The default claim of no effect or no difference"), ("What is a p-value?", "Probability of data at least this extreme if the null is true"),
       ("What is a Type I error?", "Rejecting a true null (false positive)"), ("Is statistical significance the same as practical importance?", "No, check the effect size too")]),
]}

COURSES = {c["id"]: c for c in (SQL, PY, STATS)}
LESSONS = {l["id"]: {**l, "course": c["id"]} for c in COURSES.values() for l in c["lessons"]}
QUESTIONS = {q["id"]: {**q, "lesson": l["id"]} for l in LESSONS.values() for q in l["quiz"]}
EXERCISES = {e["id"]: {**e, "lesson": l["id"]} for l in LESSONS.values() for e in l["exercises"]}
