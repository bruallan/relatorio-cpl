# app.py

import os
import calendar
from flask import Flask, render_template, request, jsonify
from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from facebook_business.exceptions import FacebookRequestError
from datetime import datetime

# --- CONFIGURAÇÃO (sem alterações) ---
# ... (mantenha a mesma configuração de antes)
MY_APP_ID = os.environ.get('MY_APP_ID')
MY_APP_SECRET = os.environ.get('MY_APP_SECRET')
MY_ACCESS_TOKEN = os.environ.get('MY_ACCESS_TOKEN')
AD_ACCOUNT_ID_1 = os.environ.get('AD_ACCOUNT_ID_1')
AD_ACCOUNT_ID_2 = os.environ.get('AD_ACCOUNT_ID_2')
AD_ACCOUNT_NAME_1 = 'Bella Serra'
AD_ACCOUNT_NAME_2 = 'Vista Bella'

FacebookAdsApi.init(MY_APP_ID, MY_APP_SECRET, MY_ACCESS_TOKEN)
app = Flask(__name__)

# --- FUNÇÃO DE BUSCA (agora aceita 'monthly') ---
def fetch_insights(account_id, start_date, end_date, increment='1'):
    try:
        if not account_id: return []
        account = AdAccount(account_id)
        params = {
            'level': 'campaign',
            'time_range': {'since': start_date, 'until': end_date},
            'time_increment': increment,
            'fields': ['campaign_name', 'spend', 'actions'],
            'action_breakdowns': ['action_type'],
        }
        return account.get_insights(params=params)
    except FacebookRequestError as e:
        print(f"Erro na API da Meta para a conta {account_id}: {e}")
        return []

# --- ROTA PARA O GRÁFICO INTERATIVO (sem alterações) ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/get_data')
def get_data():
    # ... (esta rota continua exatamente a mesma de antes)
    # ... (código omitido para encurtar, não precisa mudar)
    return jsonify({
        'account1': {'name': AD_ACCOUNT_NAME_1, 'stats': data1},
        'account2': {'name': AD_ACCOUNT_NAME_2, 'stats': data2}
    })

# --- ROTA DE DADOS ANUAIS (OTIMIZADA PARA BUSCA MENSAL) ---
@app.route('/get_yearly_data')
def get_yearly_data():
    current_year = datetime.now().year
    start_of_year = f'{current_year}-01-01'
    end_of_year = f'{current_year}-12-31'
    
    yearly_results = {
        'account1': {'name': AD_ACCOUNT_NAME_1},
        'account2': {'name': AD_ACCOUNT_NAME_2},
    }

    for acc_key, acc_id in [('account1', AD_ACCOUNT_ID_1), ('account2', AD_ACCOUNT_ID_2)]:
        # 1. FAZ UMA ÚNICA CHAMADA RÁPIDA, PEDINDO DADOS MENSAIS
        monthly_insights = fetch_insights(acc_id, start_of_year, end_of_year, increment='monthly')
        
        # 2. INICIALIZA ESTRUTURAS
        monthly_cpls = {m: 'N/D' for m in range(1, 13)}
        
        # 3. PROCESSA OS 12 PONTOS DE DADOS MENSAIS
        for insight in monthly_insights:
            campaign_name = insight.get('campaign_name', '').lower()
            if 'vaga' in campaign_name or 'vagas' in campaign_name: continue
            
            month_num = datetime.strptime(insight['date_start'], '%Y-%m-%d').month
            spend = float(insight['spend'])
            results = 0
            if 'actions' in insight:
                for action in insight['actions']:
                    if action['action_type'] == 'onsite_conversion.messaging_conversation_started_7d':
                        results = int(action['value']); break
            
            cpl = (spend / results) if results > 0 else 0
            monthly_cpls[month_num] = round(cpl, 2)

        # 4. MONTA A ESTRUTURA DE RESPOSTA PARA O FRONTEND
        final_quarterly_data = {}
        for q in range(1, 5):
            start_month = (q - 1) * 3 + 1
            q_months = range(start_month, start_month + 3)
            q_cpls = [monthly_cpls[m] for m in q_months]
            
            # A média do trimestre agora é a média dos CPLs dos 3 meses
            valid_cpls = [c for c in q_cpls if isinstance(c, (int, float))]
            avg_cpl = sum(valid_cpls) / len(valid_cpls) if valid_cpls else 'N/D'
            if isinstance(avg_cpl, float): avg_cpl = round(avg_cpl, 2)
            
            final_quarterly_data[f'q{q}'] = {
                'monthly_cpls': q_cpls, 
                'average_cpl': avg_cpl
            }
            
        final_monthly_averages = {calendar.month_name[m]: monthly_cpls[m] for m in range(1, 13)}

        yearly_results[acc_key]['quarterly_data'] = final_quarterly_data
        yearly_results[acc_key]['monthly_averages'] = final_monthly_averages
        
    return jsonify(yearly_results)

if __name__ == '__main__':
    app.run(debug=True)