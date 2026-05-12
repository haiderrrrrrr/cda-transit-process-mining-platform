# Starting Commands

Quick command reference for rebuilding and running the CDA Transit Process Mining Platform.

## 1. Create Environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 2. Rebuild Analytics Outputs

```powershell
python code\run_pipeline.py
```

This runs extraction, event-log generation, XES export, map-coordinate support, report figure generation, validation, and data-folder cleanup.

## 3. Run Streamlit Dashboard

```powershell
streamlit run code\app.py
```

## 4. Validate Outputs

```powershell
python code\validate_outputs.py
```

## 5. Clean Organized Data View

Use this if root-level generated files appear inside `data/` after experimentation:

```powershell
python code\clean_data_root.py
```

Then run the dashboard again:

```powershell
streamlit run code\app.py
```
