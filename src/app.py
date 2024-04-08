import os
import shutil
import streamlit as st
from utils.get_urls import scrape_urls
from langchain_core.messages import AIMessage, HumanMessage
from langchain_community.document_loaders import WebBaseLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from dotenv import load_dotenv
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

# Load environment variables
load_dotenv()

def get_vectorstore_from_url(url, max_depth):
    """
    Scrapes website content and creates a vector store based on the provided URL and scraping depth.

    Args:
        url (str): The URL of the website to scrape.
        max_depth (int): The maximum depth for scraping.

    Returns:
        tuple: A tuple containing the created vector store and the number of URLs scraped.
    """
    if os.path.exists('.chroma'):
        shutil.rmtree('.chroma')

    # Scrape URLs
    urls = scrape_urls(url, max_depth)

    # Load website content
    loader = WebBaseLoader(urls)
    document = loader.load()

    # Split document into chunks
    text_splitter = RecursiveCharacterTextSplitter()
    document_chunks = text_splitter.split_documents(document)

    # Create vector store
    vector_store = Chroma.from_documents(document_chunks, OpenAIEmbeddings())

    return vector_store, len(urls)

def get_context_retriever_chain(vector_store):
    """
    Creates a context-aware retriever chain based on the provided vector store.

    Args:
        vector_store: The vector store to use for retrieval.

    Returns:
        obj: The created context-aware retriever chain.
    """
    llm = ChatOpenAI()
    retriever = vector_store.as_retriever()

    # Define prompt
    prompt = ChatPromptTemplate.from_messages([
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
        ("user", "Given the above conversation, generate a search query to look up in order to get information relevant to the conversation")
    ])

    # Create retriever chain
    retriever_chain = create_history_aware_retriever(llm, retriever, prompt)

    return retriever_chain

def get_conversational_rag_chain(retriever_chain):
    """
    Creates a conversational RAG chain based on the provided retriever chain.

    Args:
        retriever_chain: The retriever chain to use for conversation.

    Returns:
        obj: The created conversational RAG chain.
    """
    llm = ChatOpenAI()

    # Define prompt
    prompt = ChatPromptTemplate.from_messages([
        ("system", "Answer the user's questions based on the below context:\n\n{context}"),
        MessagesPlaceholder(variable_name="chat_history"),
        ("user", "{input}"),
    ])

    # Create RAG chain
    stuff_documents_chain = create_stuff_documents_chain(llm,prompt)

    return create_retrieval_chain(retriever_chain, stuff_documents_chain)

def get_response(user_input):
    """
    Gets a response from the chatbot based on user input.

    Args:
        user_input (str): The user's input message.

    Returns:
        str: The chatbot's response.
    """
    retriever_chain = get_context_retriever_chain(st.session_state.vector_store)
    conversation_rag_chain = get_conversational_rag_chain(retriever_chain)

    response = conversation_rag_chain.invoke({
        "chat_history": st.session_state.chat_history,
        "input": user_input
    })

    return response['answer']

# App config
st.set_page_config(page_title="WebChat 🤖: Chat with Websites", page_icon="🤖")
st.title("WebChat 🤖: Chat with Websites")

# Initialize session state variables
if "freeze" not in st.session_state:
    st.session_state.freeze = False
if "max_depth" not in st.session_state:
    st.session_state.max_depth = 1

# Sidebar
with st.sidebar:
    st.header("WebChat 🤖")
    website_url = st.text_input("Website URL")
    
    if not st.session_state.freeze:
        st.session_state.max_depth = st.slider("Select maximum scraping depth:", 1, 5, 1)

        if st.button("Proceed"):
            st.session_state.freeze = True
    else:
        st.session_state.max_depth = st.slider("Select maximum scraping depth:", 1, 5, st.session_state.max_depth)
        st.button("Proceed", disabled=True)

    st.sidebar.markdown('---')
    st.sidebar.markdown('Connect with me:')
    st.sidebar.markdown('[LinkedIn](https://www.linkedin.com/in/saksham-chaurasia/)')
    st.sidebar.markdown('[GitHub](https://github.com/imsaksham-c)')
    st.sidebar.markdown('[Email](mailto:imsaksham.c@gmail.com)')
    
# Main content
if website_url is None or website_url == "":
    st.info("Please enter a website URL")
else:
    if st.session_state.freeze:
        # Initialize chat history and vector store if not already present
        if "chat_history" not in st.session_state:
            st.session_state.chat_history = [
                AIMessage(content="Hello, I am a bot. How can I help you?"),
            ]
        if "vector_store" not in st.session_state:
            with st.sidebar:
                with st.spinner("Scrapping Website..."):
                    st.session_state.vector_store, st.session_state.len_urls = get_vectorstore_from_url(website_url, st.session_state.max_depth)
                    st.write(f"Total Pages Scrapped: {st.session_state.len_urls}")
                    st.success("Scraping completed, 🤖 Ready!")
        else:
            with st.sidebar:
                st.write(f"Total Pages Scrapped: {st.session_state.len_urls}")
                st.success("🤖 Ready!")

        # User input
        user_query = st.text_input("Type your message here...")
        if user_query is not None and user_query != "":
            response = get_response(user_query)
            st.session_state.chat_history.append(HumanMessage(content=user_query))
            st.session_state.chat_history.append(AIMessage(content=response))

        # Display conversation
        for message in st.session_state.chat_history:
            if isinstance(message, AIMessage):
                with st.chat_message("AI"):
                    st.write(message.content)
            elif isinstance(message, HumanMessage):
                with st.chat_message("Human"):
                    st.write(message.content)
