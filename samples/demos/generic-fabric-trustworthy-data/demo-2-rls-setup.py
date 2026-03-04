"""
demo-2-rls-setup.py
====================
Microsoft Fabric - Trustworthy Data Demo Series
Demo 2: Row-Level Security on Lakehouse SQL Endpoint

PURPOSE
-------
Seeds the LH_SecurityDemo Lakehouse with the unified SalesOrders table
used to demonstrate OneLake UI-based row-level security (RLS). Run this
notebook INSIDE Fabric (attached to LH_SecurityDemo) AFTER Demo 1 setup
and AFTER OneLake security + User's identity mode are already enabled.

PREREQUISITES
-------------
- Demo 1 setup complete (OneLake security enabled, User's identity mode active)
- LH_SecurityDemo Lakehouse exists
- demo-user-north and demo-user-south provisioned with Viewer workspace role
- DefaultReader role already deleted (from Demo 1)
- NorthRegion and SouthRegion roles from Demo 1 are still in place
  (they will be supplemented by new ViewNorthOrders / ViewSouthOrders roles)

WHAT THIS SCRIPT DOES
----------------------
1. Creates a unified SalesOrders Delta table (6 rows - North + South regions)
2. Prints row counts and schema to confirm successful write
3. Prints the RLS predicate SQL strings for manual entry in the OneLake UI

MANUAL STEPS AFTER RUNNING
----------------------------
Follow Demo 2 Steps 2-3 in the demo guide to:
  - Create ViewNorthOrders role with RLS predicate on SalesOrders
  - Create ViewSouthOrders role with RLS predicate on SalesOrders
  - Run the identical SELECT and show per-user filtered results

REFERENCES
----------
https://learn.microsoft.com/en-us/fabric/onelake/security/row-level-security
https://learn.microsoft.com/en-us/fabric/onelake/security/create-manage-roles
https://learn.microsoft.com/en-us/fabric/onelake/security/data-access-control-model
"""

# ---------------------------------------------------------------------------
# Cell 1 - Imports and SparkSession
# ---------------------------------------------------------------------------
from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType, DoubleType

spark = SparkSession.builder.getOrCreate()
print(f"Spark version: {spark.version}")

# ---------------------------------------------------------------------------
# Cell 2 - Define schema and unified dataset
# ---------------------------------------------------------------------------
orders_schema = StructType([
    StructField("OrderID",  StringType(), False),
    StructField("SalesRep", StringType(), False),
    StructField("Region",   StringType(), False),
    StructField("Amount",   DoubleType(), False),
])

orders_data = [
    ("O001", "Alice", "North", 52000.0),
    ("O002", "Bob",   "North", 47000.0),
    ("O003", "Carol", "North", 61000.0),
    ("O004", "Dave",  "South", 39000.0),
    ("O005", "Eve",   "South", 44500.0),
    ("O006", "Frank", "South", 58000.0),
]

# ---------------------------------------------------------------------------
# Cell 3 - Write SalesOrders Delta table
# ---------------------------------------------------------------------------
df_orders = spark.createDataFrame(orders_data, orders_schema)
df_orders.write.format("delta").mode("overwrite").saveAsTable("SalesOrders")

count_orders = spark.table("SalesOrders").count()
print(f"SalesOrders created - row count: {count_orders}")

# ---------------------------------------------------------------------------
# Cell 4 - Verification: preview the table
# ---------------------------------------------------------------------------
print("\n--- SalesOrders preview ---")
spark.table("SalesOrders").show()

print("\nTable written successfully. Proceed with OneLake RLS role creation in the Fabric portal.")

# ---------------------------------------------------------------------------
# Cell 5 - RLS predicates to copy into OneLake UI
# ---------------------------------------------------------------------------
RLS_PREDICATES = {
    "ViewNorthOrders": "SELECT * FROM dbo.SalesOrders WHERE Region = 'North'",
    "ViewSouthOrders": "SELECT * FROM dbo.SalesOrders WHERE Region = 'South'",
}

print("\n--- RLS predicates (copy-paste into OneLake security > Row security) ---")
for role_name, predicate in RLS_PREDICATES.items():
    print(f"\nRole: {role_name}")
    print(f"  Predicate: {predicate}")

# ---------------------------------------------------------------------------
# Cell 6 - Validation query to run at SQL analytics endpoint
# ---------------------------------------------------------------------------
VALIDATION_QUERY = """
-- Run this IDENTICAL query as demo-user-north, demo-user-south, and presenter.
-- demo-user-north returns O001, O002, O003 only.
-- demo-user-south returns O004, O005, O006 only.
-- Presenter (admin) returns all 6 rows (workspace role bypasses OneLake security).

SELECT OrderID, SalesRep, Region, Amount
FROM SalesOrders
ORDER BY Region, OrderID;
"""

print("\n--- Validation query for SQL analytics endpoint ---")
print(VALIDATION_QUERY)

# ---------------------------------------------------------------------------
# Cell 7 - RLS behavior notes (display for presenter reference)
# ---------------------------------------------------------------------------
RLS_NOTES = """
IMPORTANT BEHAVIOR NOTES (share with audience during demo):
-----------------------------------------------------------
1. String comparison in RLS predicates is case-INSENSITIVE.
2. Supported operators: =, <>, >, >=, <, <=, IN, NOT, AND, OR, TRUE, FALSE, NULL
3. Dynamic functions like USER_NAME() are NOT supported in Public Preview.
4. Multi-table predicates (JOIN across tables) are NOT supported in Public Preview.
5. If a user belongs to two roles - one with RLS, one without - MOST PERMISSIVE WINS.
   The user without RLS on the permissive role sees all rows. Avoid overlapping roles.
6. The same OneLake RLS predicate enforces across:
   - SQL analytics endpoint (T-SQL SELECT)
   - Spark (DataFrame reads via Lakehouse connector)
   - Power BI (Import and DirectLake modes)
"""

print(RLS_NOTES)

# ---------------------------------------------------------------------------
# Cell 8 - Cleanup helper (run ONLY to reset demo environment)
# ---------------------------------------------------------------------------
def cleanup_demo_tables():
    """
    Drop the SalesOrders table to reset this demo.
    Uncomment the drop statement when intentional cleanup is needed.
    """
    # spark.sql("DROP TABLE IF EXISTS SalesOrders")
    print("Cleanup helper loaded. Uncomment drop statement to execute.")

cleanup_demo_tables()
