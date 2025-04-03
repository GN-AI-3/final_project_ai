from dotenv import load_dotenv
from langchain_core.example_selectors import SemanticSimilarityExampleSelector
from langchain_openai import OpenAIEmbeddings, ChatOpenAI
from langchain_community.vectorstores import InMemoryVectorStore
from langchain_core.prompts import ChatPromptTemplate, FewShotChatMessagePromptTemplate

# 환경 변수 로드
load_dotenv()

# 예제 데이터 정의
examples = [
    {"input": "2 🦜 2", "output": "4"},
    {"input": "2 🦜 3", "output": "5"},
    {"input": "2 🦜 4", "output": "6"},
    {"input": "What did the cow say to the moon?", "output": "nothing at all"},
    {
        "input": "Write me a poem about the moon",
        "output": "One for the moon, and one for me, who are we to talk about the moon?",
    },
]

# 벡터 저장소 초기화
embeddings = OpenAIEmbeddings()
vectorstore = InMemoryVectorStore(embeddings)

# 예제 데이터를 벡터 저장소에 추가
to_vectorize = [" ".join(example.values()) for example in examples]
for i, text in enumerate(to_vectorize):
    vectorstore.add_texts([text], metadatas=[examples[i]])

# 예제 선택기 초기화
example_selector = SemanticSimilarityExampleSelector(vectorstore=vectorstore, k=2)

# Few-shot 프롬프트 템플릿 정의
few_shot_prompt = FewShotChatMessagePromptTemplate(
    input_variables=["input"],
    example_selector=example_selector,
    example_prompt=ChatPromptTemplate.from_messages(
        [("human", "{input}"), ("ai", "{output}")]
    ),
)

# 최종 프롬프트 정의
final_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a wondrous wizard of math."),
        few_shot_prompt,
        ("human", "{input}"),
    ]
)

# 체인 구성 및 실행
chain = final_prompt | ChatOpenAI(model="gpt-4o-mini", temperature=0.0)
result = chain.invoke({"input": "What's 3 🦜 3?"})
print(result)