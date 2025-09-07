<div align="center">

# 🏎️ F1 Strategy Manager

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/) [![Streamlit](https://img.shields.io/badge/Streamlit-1.28%2B-red)](https://streamlit.io/) [![PyTorch](https://img.shields.io/badge/PyTorch-2.0%2B-orange)](https://pytorch.org/) [![Pandas](https://img.shields.io/badge/Pandas-2.0%2B-purple)](https://pandas.pydata.org/) [![XGBoost](https://img.shields.io/badge/XGBoost-1.7%2B-green)](https://xgboost.readthedocs.io/) [![OpenCV](https://img.shields.io/badge/OpenCV-4.8%2B-blue)](https://opencv.org/) [![FastF1](https://img.shields.io/badge/FastF1-3.1%2B-red)](https://github.com/theOehrly/Fast-F1) [![License](https://img.shields.io/badge/License-MIT-green)](LICENSE) [![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/VforVitorio/F1_Strat_Manager)

</div>

**Revolutionizing strategic decision-making in Formula 1 through AI-powered models, computer vision, and expert systems. For a deeper insight, see the project's [paper here](documents/F1_Strategy_Manager_AI.pdf).**

<p align="center">
  <img
    src="documents/banner/f1_strat_manager_banner.jpeg"
    alt="Banner VforVitorio"
    style="width:85%; max-width:900px; aspect-ratio:21/9; border-radius:20px;"
  />
</p>

---

## 🚀 Project Overview

In Formula 1, strategic decisions must be made within seconds while considering complex, dynamic variables like weather, tire wear, track position, and fuel. The **F1 Strategy Manager** project proposes a solution by integrating advanced predictive models and expert systems to support real-time strategy recommendations.

---

## 📚 Docs

> [!WARNING]
> **Documentation & Wiki**
>
> This repository has a wiki generated automatically with GitHub Actions, based on **DeepWiki**.
>
> However, the documentation on the **DeepWiki** page is much better structured and highly recommended for obtaining clearer and more navigable information about the project.
>
> 👉 **Access the full documentation here**: [https://deepwiki.com/VforVitorio/F1_Strat_Manager](https://deepwiki.com/VforVitorio/F1_Strat_Manager)

---

## 🧠 Main Objective

Develop an **intelligent strategy recommender** that, based on processed race data, can offer optimized strategic decisions to the team in real time.

---

## 🧩 Project Structure

### 📦 Data Extraction & Preparation

- **Sources**: FastF1, OpenF1, Roboflow
- **Data Types**:
  - Weather data
  - Track and race conditions
  - Team radio communications
  - Video frames (used for computer vision models)
- **Augmentation & Labelling**:
  - Enhanced image dataset using flips, rotation, blur, etc.
  - Manual labelling of radios (sentiment, intent, NER)
- **Pipeline**:
  - All data merged into a single structured DataFrame
  - Generated synthetic variables and filtered irrelevant ones
  - Divided data by stint and lap sequences

### 🎯 Machine Learning Models

- **XGBoost** : Lap time prediction with MAE = 0.09s and RMSE = 0.15s
- **TCN (Temporal Convolutional Networks)** : For tire degradation modeling
- **YOLOv8** : Team identification from race footage with >90% mAP50
  > ⚠️ This section is no longer updated. Further development continues in an independent repository, now using YOLOv12.  
  > See: [VforVitorio/F1_AI_team_detection](https://github.com/VforVitorio/F1_AI_team_detection)
- **Whisper Turbo + BERT** : NLP pipeline for radio communication analysis

### 🧠 Expert System

- Developed using the **Experta** framework.
- Integrates all processed data and model results for strategy suggestion.

### 📊 App Interface

- Built using **Streamlit**.
- Allows:
  - Model interaction per section (Vision, NLP, ML)
  - Visual exploration and graphing
  - Chatbot Q&A via LLM for post-race reports and image analysis using Llama3.2-vision

---

## 🖥️ Environment Setup & Usage

### ⚙️ Requirements

- Python 3.10+
- CUDA-compatible GPU (for local training and video inference)
- Pipenv or venv (recommended)

### 📦 Main Libraries

```bash
pip install -r requirements.txt
```

If `requirements.txt` is not available, some key dependencies are:

- `pandas`, `numpy`, `matplotlib`, `seaborn`
- `fastf1`, `openf1`
- `opencv-python`, `roboflow`
- `torch`, `pytorch-lightning`, `xgboost`
- `transformers`, `whisper`, `experta`
- `streamlit`, `plotly`

### 🧪 Running the Project

1. Clone the repository:

```bash
git clone https://github.com/VforVitorio/F1_Strat_Manager.git
cd F1_Strat_Manager
```

2. Activate your environment:

```bash
python -m venv venv
source venv/bin/activate  # On Windows use venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Run the app:

```bash
streamlit run app/main.py
```

> Each major module (NLP, Vision, ML) is in its own subfolder with Jupyter notebooks and utility scripts.

---

## 🤝 About This Project

This is a **personal project** that will serve as my **Final Degree Project (Thesis)**. While this is primarily an academic endeavor, I welcome feedback, suggestions, and collaboration from the F1 and AI community.

If you'd like to report bugs, suggest features, or collaborate, please use the [Issue Templates](ISSUE_TEMPLATES.md) to ensure clear communication.
