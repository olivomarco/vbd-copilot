"""
demo-1-onelake-security-setup.py
=================================
Microsoft Fabric - Trustworthy Data Demo Series
Demo 1: OneLake Security Role Layering

PURPOSE
-------
Seeds the LH_SecurityDemo Lakehouse with two regional sales tables used
in the live OneLake security demo. Run this notebook INSIDE Fabric
(attach to LH_SecurityDemo) before the session begins.

PREREQUISITES
-------------
- Fabric workspace on F-capacity (not trial)
- Lakehouse named LH_SecurityDemo exists in the workspace
- This notebook is attached to LH_SecurityDemo
- Two Entra test users provisioned:
    demo-user-north@<tenant>.onmicrosoft.com
    demo-user-south@<tenant>.onmicrosoft.com
- Both users have Viewer workspace role + Fabric Read item permission on LH_SecurityDemo

WHAT THIS SCRIPT DOES
----------------------
1. Creates NorthSalesData Delta table (3 rows, Region=North)
2. Creates SouthSalesData Delta table (3 rows, Region=South)
3. Prints row counts to confirm successful writes

MANUAL STEPS AFTER RUNNING
----------------------------
Follow Demo 1 Step 2 onward in the demo guide to:
  - Enable OneLake security on the Lakehouse
  - Delete DefaultReader role
  - Create NorthRegion and SouthRegion OneLake roles
  - Switch SQL endpoint to User's identity mode
  - Validate with side-by-side browser windows

REFERENCES
----------
https://learn.microsoft.com/en-us/fabric/onelake/security/get-started-onelake-security
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
# Cell 2 - Define shared schema
# ---------------------------------------------------------------------------
sales_schema = StructType([
    StructField("OrderID",  StringType(), False),
    StructField("SalesRep", StringType(), False),
    StructField("Region",   StringType(), False),
    StructField("Amount",   DoubleType(), False),
])

# ---------------------------------------------------------------------------
# Cell 3 - Load NorthSalesData table
# ---------------------------------------------------------------------------
north_data = [
    ("N001", "Alice", "North", 52000.0),
    ("N002", "Bob",   "North", 47000.0),
    ("N003", "Carol", "North", 61000.0),
]

df_north = spark.createDataFrame(north_data, sales_schema)
df_north.write.format("delta").mode("overwrite").saveAsTable("NorthSalesData")

count_north = spark.table("NorthSalesData").count()
print(f"NorthSalesData created - row count: {count_north}")

# ---------------------------------------------------------------------------
# Cell 4 - Load SouthSalesData table
# ---------------------------------------------------------------------------
south_data = [
    ("S001", "Dave",  "South", 39000.0),
    ("S002", "Eve",   "South", 44500.0),
    ("S003", "Frank", "South", 58000.0),
]

df_south = spark.createDataFrame(south_data, sales_schema)
df_south.write.format("delta").mode("overwrite").saveAsTable("SouthSalesData")

count_south = spark.table("SouthSalesData").count()
print(f"SouthSalesData created - row count: {count_south}")

# ---------------------------------------------------------------------------
# Cell 5 - Verification: preview both tables
# ---------------------------------------------------------------------------
print("\n--- NorthSalesData preview ---")
spark.table("NorthSalesData").show()

print("\n--- SouthSalesData preview ---")
spark.table("SouthSalesData").show()

print("\nSetup complete. Proceed with manual OneLake security configuration in the Fabric portal.")

# ---------------------------------------------------------------------------
# Cell 6 - SQL endpoint validation queries (copy-paste into SQL analytics endpoint)
# ---------------------------------------------------------------------------
VALIDATION_QUERIES = """
-- Run each query as demo-user-north, demo-user-south, and as presenter (admin).
-- Expected results are commented next to each query.

-- Query 1: Should return 3 rows for demo-user-north, ACCESS DENIED for demo-user-south
SELECT * FROM NorthSalesData;

-- Query 2: Should return 3 rows for demo-user-south, ACCESS DENIED for demo-user-north
SELECT * FROM SouthSalesData;

-- Query 3: Presenter sees all data (admin bypasses OneLake security)
SELECT 'NorthSalesData' AS TableName, COUNT(*) AS RowCount FROM NorthSalesData
UNION ALL
SELECT 'SouthSalesData', COUNT(*) FROM SouthSalesData;
"""

print("Validation queries for SQL analytics endpoint:")
print(VALIDATION_QUERIES)

# ---------------------------------------------------------------------------
# Cell 7 - Cleanup helper (run ONLY to reset demo environment)
# ---------------------------------------------------------------------------
def cleanup_demo_tables():
    """
    Drop both demo tables to reset the environment.
    USE SPARINGLY - this permanently deletes the data.
    Uncomment the drop statements when intentional cleanup is needed.
    """
    # spark.sql("DROP TABLE IF EXISTS NorthSalesData")
    # spark.sql("DROP TABLE IF EXISTS SouthSalesData")
    print("Cleanup helper loaded. Uncomment drop statements to execute.")

cleanup_demo_tables()
