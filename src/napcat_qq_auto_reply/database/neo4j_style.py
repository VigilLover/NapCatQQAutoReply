import asyncio
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class StyleMatch:
    text: str
    score: float


class Neo4jStyleRepository:
    def __init__(self, driver, embedder):
        self.driver = driver
        self.embedder = embedder

    async def search(self, persona, query, top_k=8):
        embedding = await asyncio.to_thread(self.embedder.embed_query, query)

        def execute():
            with self.driver.session(default_access_mode="READ") as session:
                result = session.run(
                    """
                    CALL db.index.vector.queryNodes(
                        'sentence_embeddings', $top_k, $embedding
                    )
                    YIELD node, score
                    WHERE node.userid = $persona
                    RETURN node.text AS text, score
                    ORDER BY score DESC
                    """,
                    top_k=top_k,
                    embedding=embedding,
                    persona=persona,
                )
                return result.data()

        rows = await asyncio.to_thread(execute)
        return [StyleMatch(text=str(row["text"]), score=float(row["score"])) for row in rows]

    async def close(self) -> None:
        await asyncio.to_thread(self.driver.close)


def create_neo4j_style_repository(url: str, auth: tuple[str, str] | None, embedder):
    from neo4j import GraphDatabase

    driver = GraphDatabase.driver(url, auth=auth)
    return Neo4jStyleRepository(driver=driver, embedder=embedder)
