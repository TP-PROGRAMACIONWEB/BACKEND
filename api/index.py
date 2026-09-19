"""Punto de entrada del backend en Vercel.

Vercel corre cada request como una función serverless: busca este archivo y
toma la variable `app` (ASGI). La app es exactamente la misma que levanta
`iniciar_backend.bat` en local — acá no hay lógica propia, solo el enganche.
"""

from app.main import app  # noqa: F401 — Vercel lo descubre por nombre
