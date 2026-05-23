from pydantic import BaseModel, HttpUrl


class FileRequest(BaseModel):
    url: HttpUrl | None = None
    engine: str | None = None


class Segment(BaseModel):
    start: float
    end: float
    text: str


class FileResponse(BaseModel):
    text: str
    segments: list[Segment]
    language: str | None = None
    duration: float | None = None
    engine: str


class StreamResponse(BaseModel):
    text: str
    is_final: bool
