 # AndreOlesen-IND320
   Project work in IND320 Data to Decision (NMBU), autumn 2026.

   - Streamlit app: https://andreolesen-ind320.streamlit.app/
   - Notebooks: `IND320_part1.ipynb`, `ind320_part2.ipynb`
   - Data: NVE Magasinstatistikk API (reservoirs) and ENTSO-E Transparency Platform (cross-border flows), stored in MongoDB Atlas


## Run locally
```
pip install -r requirements.txt
streamlit run streamlit_app.py
```
 The app needs `.streamlit/secrets.toml` with the MongoDB URI (not included in the repository). 
