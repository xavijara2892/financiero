# Xavier Finance Pro

Aplicación web en Streamlit para evaluar financiamiento y rentabilidad de proyectos energéticos.

## Ejecutar localmente

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Deploy rápido en Streamlit Community Cloud

1. Crear un repositorio en GitHub.
2. Subir estos archivos:
   - `app.py`
   - `requirements.txt`
3. Entrar a Streamlit Community Cloud.
4. Elegir el repositorio y desplegar apuntando a `app.py`.

## Deploy en Render

Este paquete también incluye `render.yaml`.

1. Subir el proyecto a GitHub.
2. Crear un nuevo Blueprint en Render.
3. Seleccionar el repositorio.
4. Render detectará `render.yaml` y desplegará la app.

## Archivos incluidos

- `app.py`: aplicación principal
- `requirements.txt`: dependencias
- `render.yaml`: configuración para Render
- `.streamlit/config.toml`: configuración del servidor
