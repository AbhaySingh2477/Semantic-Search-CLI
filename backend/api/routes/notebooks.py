"""
Notebook Routes — Manage notebooks.
"""

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel

from domain.entities import Notebook
from infrastructure.repositories.sqlite_notebook_repo import SQLiteNotebookRepository, get_notebook_repo

router = APIRouter(tags=["notebooks"])

class CreateNotebookRequest(BaseModel):
    name: str
    description: str = ""
    color: str = "#7c6bf5"
    icon: str = "book-open"

class NotebookResponse(BaseModel):
    id: str
    name: str
    description: str
    color: str
    icon: str
    document_count: int
    created_at: str
    updated_at: str

@router.get("/notebooks", response_model=list[NotebookResponse])
async def list_notebooks(
    repo: SQLiteNotebookRepository = Depends(get_notebook_repo)
):
    notebooks = await repo.list_notebooks()
    return [
        NotebookResponse(
            id=nb.id,
            name=nb.name,
            description=nb.description,
            color=nb.color,
            icon=nb.icon,
            document_count=nb.document_count,
            created_at=nb.created_at.isoformat(),
            updated_at=nb.updated_at.isoformat(),
        ) for nb in notebooks
    ]

@router.post("/notebooks", response_model=NotebookResponse)
async def create_notebook(
    req: CreateNotebookRequest,
    repo: SQLiteNotebookRepository = Depends(get_notebook_repo)
):
    nb = Notebook(
        name=req.name,
        description=req.description,
        color=req.color,
        icon=req.icon,
    )
    created_nb = await repo.create_notebook(nb)
    return NotebookResponse(
        id=created_nb.id,
        name=created_nb.name,
        description=created_nb.description,
        color=created_nb.color,
        icon=created_nb.icon,
        document_count=created_nb.document_count,
        created_at=created_nb.created_at.isoformat(),
        updated_at=created_nb.updated_at.isoformat(),
    )

@router.get("/notebooks/{notebook_id}", response_model=NotebookResponse)
async def get_notebook(
    notebook_id: str,
    repo: SQLiteNotebookRepository = Depends(get_notebook_repo)
):
    nb = await repo.get_notebook(notebook_id)
    if not nb:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return NotebookResponse(
        id=nb.id,
        name=nb.name,
        description=nb.description,
        color=nb.color,
        icon=nb.icon,
        document_count=nb.document_count,
        created_at=nb.created_at.isoformat(),
        updated_at=nb.updated_at.isoformat(),
    )

@router.delete("/notebooks/{notebook_id}")
async def delete_notebook(
    notebook_id: str,
    repo: SQLiteNotebookRepository = Depends(get_notebook_repo)
):
    success = await repo.delete_notebook(notebook_id)
    if not success:
        raise HTTPException(status_code=404, detail="Notebook not found")
    return {"status": "success"}
