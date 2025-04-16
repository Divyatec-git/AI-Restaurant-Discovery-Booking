# from fastapi import FastAPI, HTTPException, Request
# from langchain_core.pydantic_v1 import BaseModel
# from langchain.chains import create_sql_query_chain
# from langchain_google_genai import GoogleGenerativeAI
# from sqlalchemy import create_engine
# from sqlalchemy.exc import ProgrammingError
# from langchain_community.utilities import SQLDatabase
# import os,re
# from dotenv import load_dotenv

# load_dotenv()

# # Database connection parameters
# db_user = os.getenv("DB_USER")
# db_password = os.getenv("DB_PASSWORD")
# db_host = os.getenv("DB_HOST")
# db_name = os.getenv("DB_NAME")

# # Create SQLAlchemy engine
# engine = create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")

# # Initialize SQLDatabase
# db = SQLDatabase(engine, sample_rows_in_table_info=3)

# # Initialize LLM
# llm = GoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=os.getenv("GENAI_API_KEY"))

# # Create SQL query chain
# chain = create_sql_query_chain(llm, db)

# # FastAPI instance
# app = FastAPI()

# # Request model
# class QueryRequest(BaseModel):
#     question: str

# @app.post("/execute_query")
# async def execute_query(request: Request):
#     try:
#         body = await request.json()  # ✅ Debugging: Print the raw request
#         print(f"Received request body: {body}")

#         # Ensure "question" key exists
#         if "question" not in body:
#             raise HTTPException(status_code=400, detail="Missing 'question' field in request")

#         question = body["question"]

#         # Generate SQL query from question
#         sql_query = chain.invoke({"question": question})

#         # ✅ Remove Markdown-style backticks and "sql" labels
#         sql_query = re.sub(r"```sql|```", "", sql_query).strip()

#         # Execute the query
#         result = db.run(sql_query)

#         # ✅ Convert result into natural language using LLM
#         explanation_prompt = f"Convert this SQL query result into a natural language response:\n\nQuery: {sql_query}\nResult: {result}"
#         nlp_response = llm.invoke(explanation_prompt)

#         return {"query": sql_query, "result": result,"nlp_response": nlp_response}  # 🔥 NLP interpretation of SQL result}

#     except ProgrammingError as e:
#         print(e)
#         raise HTTPException(status_code=400, detail=str(e))

import re
import os
from fastapi import FastAPI, HTTPException, Request
from sqlalchemy.exc import ProgrammingError
from langchain.chains import create_sql_query_chain
from langchain_google_genai import GoogleGenerativeAI
from langchain_community.utilities import SQLDatabase
from sqlalchemy import create_engine
from dotenv import load_dotenv
from urllib.parse import quote_plus

load_dotenv()

# Database connection
db_user = os.getenv("DB_USER")
db_password = quote_plus(os.getenv("DB_PASSWORD"))
db_host = os.getenv("DB_HOST")
db_name = os.getenv("DB_NAME")

engine = create_engine(f"mysql+pymysql://{db_user}:{db_password}@{db_host}/{db_name}")
db = SQLDatabase(engine, sample_rows_in_table_info=3)

# Initialize LLM
llm = GoogleGenerativeAI(model="gemini-2.0-flash", google_api_key=os.getenv("GENAI_API_KEY"))

# Create SQL query chain
chain = create_sql_query_chain(llm, db)

# FastAPI instance
app = FastAPI()

@app.post("/execute_query")
async def book(request: Request):
    try:
        body = await request.json()
        print(f"Received booking request: {body}")

        if "question" not in body:
            raise HTTPException(status_code=400, detail="Missing 'question' field in request")

        question = body["question"]
        print(question,'-----')

        # ✅ Generate SQL to check availability AND book in a single query
        full_query = chain.invoke({
            "question": f"Check if the booking slot is available and insert a booking if available: {question}"
        })
        full_query = re.sub(r"```sql|```", "", full_query).strip()
        print(f"Generated SQL: {full_query}")

        # Execute the generated SQL
        result = db.run(full_query)

        # ✅ Convert result into natural language
        explanation_prompt = f"Convert this SQL execution result into a natural language response:\n\nQuery: {full_query}\nResult: {result}"
        nlp_response = llm.invoke(explanation_prompt)

        return {
            "query": full_query,
            "result": result,
            "message": nlp_response  # 🔥 Final NLP response
        }

    except ProgrammingError as e:
        print(e,'--------------')
        raise HTTPException(status_code=400, detail=str(e))
