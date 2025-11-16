// Global variables
let pnlChart, signalRateChart, currentChartPeriod = '1h';
let pnlData = { labels: [], realized: [], unrealized: [], total: [] };
let signalCount = 0;
let lastSignalTime = Date.now();

async function fetchJSON(url){
  const r=await fetch(url);return r.json()
}

function updateSystemSummary(d){
  const h=document.getElementById('sys-healthy');
  const s=document.getElementById('sys-strategies');
  const p=document.getElementById('sys-positions');
  const g=document.getElementById('sys-signals');
  const indicator=document.getElementById('sys-status-indicator');
  const uptime=document.getElementById('sys-uptime');
  
  if(h)h.textContent=d.healthy?"yes":"no";
  if(s)s.textContent=d.strategies;
  if(p)p.textContent=d.positions;
  if(g)g.textContent=d.processed_signals;
  
  if(indicator){
    indicator.className='status-indicator '+(d.healthy?'status-online':'status-offline');
  }
  
  if(uptime && d.startup_time){
    const uptimeMs=Date.now()-new Date(d.startup_time).getTime();
    uptime.textContent=formatUptime(uptimeMs);
  }
}

function formatUptime(ms){
  const seconds=Math.floor(ms/1000);
  const minutes=Math.floor(seconds/60);
  const hours=Math.floor(minutes/60);
  const days=Math.floor(hours/24);
  
  if(days>0)return`${days}d ${hours%24}h`;
  if(hours>0)return`${hours}h ${minutes%60}m`;
  if(minutes>0)return`${minutes}m ${seconds%60}s`;
  return`${seconds}s`;
}

function renderPositions(items){
  const tbody=document.getElementById('positionsBody');
  if(!tbody)return;
  tbody.innerHTML='';
  
  let totalPnl=0;
  for(const it of items){
    const pnl=(it.realized_pnl||0)+(it.unrealized_pnl||0);
    totalPnl+=pnl;
    const pnlPercent=it.average_price>0?((pnl/(Math.abs(it.net_quantity)*it.average_price))*100):0;
    
    const tr=document.createElement('tr');
    tr.innerHTML=`
      <td><strong>${it.symbol}</strong></td>
      <td class="text-end ${it.net_quantity>=0?'text-success':'text-danger'}">${it.net_quantity}</td>
      <td class="text-end">₹${it.average_price.toFixed(2)}</td>
      <td class="text-end">₹${(it.last_price||0).toFixed(2)}</td>
      <td class="text-end ${pnl>=0?'text-success':'text-danger'} fw-bold">₹${pnl.toFixed(2)}</td>
      <td class="text-end ${pnlPercent>=0?'text-success':'text-danger'} fw-bold">${pnlPercent.toFixed(2)}%</td>
    `;
    tbody.appendChild(tr)
  }
  
  // Update active symbols count
  document.getElementById('active-symbols').textContent=items.length;
}

function renderSignals(items){
  const list=document.getElementById('signalsList');
  if(!list)return;
  list.innerHTML='';
  
  // Update signal rate
  if(items.length>0){
    signalCount+=items.length;
    const timeDiff=(Date.now()-lastSignalTime)/1000/60; // minutes
    if(timeDiff>0){
      const rate=(signalCount/timeDiff).toFixed(1);
      document.getElementById('signal-rate').textContent=`${rate}/min`;
    }
  }
  
  for(const s of items.slice(0,10)){ // Show only last 10 signals
    const el=document.createElement('div');
    el.className='list-group-item';
    const signalType=s.final_signal?.signal_type||'';
    const strength=s.final_signal?.strength||0;
    const timestamp=new Date(s.timestamp).toLocaleTimeString();
    
    el.innerHTML=`
      <div class="d-flex justify-content-between align-items-center">
        <div>
          <strong>${s.symbol}</strong> 
          <span class="badge ${getSignalBadgeClass(signalType)}">${signalType}</span>
        </div>
        <small class="text-muted">${timestamp}</small>
      </div>
      <div class="d-flex justify-content-between align-items-center mt-1">
        <small>Qty: ${s.final_signal?.quantity||0}</small>
        <div class="progress" style="width: 60px; height: 4px;">
          <div class="progress-bar" role="progressbar" style="width: ${(strength*100)}%"></div>
        </div>
      </div>
    `;
    list.appendChild(el)
  }
  
  // Update last update time
  document.getElementById('last-update').textContent=new Date().toLocaleTimeString();
}

function getSignalBadgeClass(signalType){
  switch(signalType.toLowerCase()){
    case 'buy':
    case 'bullish':
      return 'bg-success';
    case 'sell':
    case 'bearish':
      return 'bg-danger';
    case 'hold':
    case 'neutral':
      return 'bg-secondary';
    default:
      return 'bg-info';
  }
}

let pnlChart;
function initCharts(){
  const ctx=document.getElementById('pnlChart');
  if(!ctx)return;
  
  pnlChart=new Chart(ctx,{
    type:'line',
    data:{
      labels:[],
      datasets:[
        {
          label:'Total P&L',
          data:[],
          borderColor:'#4bd',
          backgroundColor:'rgba(74,187,221,0.1)',
          tension:.2,
          fill:true
        },
        {
          label:'Realized',
          data:[],
          borderColor:'#28a745',
          backgroundColor:'rgba(40,167,69,0.1)',
          tension:.2,
          fill:false
        },
        {
          label:'Unrealized',
          data:[],
          borderColor:'#ffc107',
          backgroundColor:'rgba(255,193,7,0.1)',
          tension:.2,
          fill:false
        }
      ]
    },
    options:{
      responsive:true,
      animation:false,
      scales:{
        x:{display:true,grid:{color:'rgba(255,255,255,0.1)'}},
        y:{display:true,grid:{color:'rgba(255,255,255,0.1)'}}
      },
      plugins:{
        legend:{labels:{color:'#e8e8e8'}},
        tooltip:{
          backgroundColor:'#2b2f33',
          titleColor:'#e8e8e8',
          bodyColor:'#e8e8e8',
          borderColor:'#3a3f44',
          borderWidth:1
        }
      }
    }
  })
}

function pushPnlPoint(realized,unrealized){
  if(!pnlChart)return;
  
  const total=(realized||0)+(unrealized||0);
  const now=new Date();
  const timeLabel=now.toLocaleTimeString();
  
  // Update data arrays
  pnlData.labels.push(timeLabel);
  pnlData.realized.push(realized||0);
  pnlData.unrealized.push(unrealized||0);
  pnlData.total.push(total);
  
  // Keep only last 120 points
  if(pnlData.labels.length>120){
    pnlData.labels.shift();
    pnlData.realized.shift();
    pnlData.unrealized.shift();
    pnlData.total.shift();
  }
  
  // Update chart
  pnlChart.data.labels=pnlData.labels;
  pnlChart.data.datasets[0].data=pnlData.total;
  pnlChart.data.datasets[1].data=pnlData.realized;
  pnlChart.data.datasets[2].data=pnlData.unrealized;
  
  pnlChart.update('none'); // Update without animation
  
  // Update P&L summary
  updatePnlSummary(realized,unrealized,total);
}

function updatePnlSummary(realized,unrealized,total){
  const realizedEl=document.getElementById('pnl-realized');
  const unrealizedEl=document.getElementById('pnl-unrealized');
  const totalEl=document.getElementById('pnl-total');
  const progressEl=document.getElementById('pnl-progress');
  
  if(realizedEl)realizedEl.textContent=`₹${(realized||0).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
  if(unrealizedEl)unrealizedEl.textContent=`₹${(unrealized||0).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
  if(totalEl)totalEl.textContent=`₹${(total||0).toLocaleString('en-IN', {minimumFractionDigits: 2})}`;
  
  // Update progress bar (assuming max P&L of ₹100,000 for demo)
  const maxPnl=100000;
  const progressPercent=Math.min(Math.abs(total)/maxPnl*100,100);
  if(progressEl){
    progressEl.style.width=`${progressPercent}%`;
    progressEl.className=`progress-bar ${total>=0?'bg-success':'bg-danger'}`;
  }
}

async function refresh(){
  try{
    const [st,pos,sig,pnl,risk]=await Promise.all([
      fetchJSON('/api/status'),
      fetchJSON('/api/positions'),
      fetchJSON('/api/signals?limit=20'),
      fetchJSON('/api/pnl'),
      fetchJSON('/api/risk')
    ]);
    
    updateSystemSummary(st);
    renderPositions(pos.positions||[]);
    renderSignals(sig.signals||[]);
    pushPnlPoint(pnl.realized,pnl.unrealized);
    updateRiskMetrics(risk);
    
  }catch(error){
    console.error('Failed to refresh dashboard:',error);
  }
}

function updateRiskMetrics(riskData){
  const riskLevelEl=document.getElementById('risk-level');
  const maxDrawdownEl=document.getElementById('max-drawdown');
  const sharpeRatioEl=document.getElementById('sharpe-ratio');
  
  if(riskData.risk_state){
    const riskLevel=riskData.risk_state.risk_level||'unknown';
    if(riskLevelEl){
      riskLevelEl.textContent=riskLevel.toUpperCase();
      riskLevelEl.className=`badge bg-${getRiskColor(riskLevel)}`;
    }
    
    if(maxDrawdownEl){
      const drawdown=riskData.portfolio_state?.drawdown||0;
      maxDrawdownEl.textContent=`${drawdown.toFixed(2)}%`;
      maxDrawdownEl.className=`fw-bold ${drawdown<-5?'text-danger':'text-success'}`;
    }
    
    if(sharpeRatioEl){
      const sharpe=riskData.portfolio_state?.sharpe_ratio||0;
      sharpeRatioEl.textContent=sharpe.toFixed(2);
    }
  }
}

function getRiskColor(riskLevel){
  switch(riskLevel.toLowerCase()){
    case 'low':return'success';
    case 'medium':return'warning';
    case 'high':return'danger';
    default:return'secondary';
  }
}

function setChartPeriod(period){
  currentChartPeriod=period;
  
  // Update button states
  document.querySelectorAll('.btn-group .btn').forEach(btn=>{
    btn.classList.remove('active');
  });
  event.target.classList.add('active');
  
  // Clear existing data and reload
  pnlData={labels:[],realized:[],unrealized:[],total:[]};
  if(pnlChart){
    pnlChart.data.labels=[];
    pnlChart.data.datasets.forEach(dataset=>dataset.data=[]);
    pnlChart.update();
  }
}

function exportData(){
  // Export current dashboard data as JSON
  const data={
    timestamp:new Date().toISOString(),
    pnlData:pnlData,
    signalCount:signalCount,
    chartPeriod:currentChartPeriod
  };
  
  const blob=new Blob([JSON.stringify(data,null,2)],{type:'application/json'});
  const url=URL.createObjectURL(blob);
  const a=document.createElement('a');
  a.href=url;
  a.download=`fortress-dashboard-${new Date().toISOString().slice(0,10)}.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function connectWS(){
  try{
    const ws=new WebSocket((location.protocol==='https:'?'wss':'ws')+'://'+location.host+'/ws/events');
    
    ws.onmessage=(ev)=>{
      try{
        const data=JSON.parse(ev.data);
        
        // Handle different event types
        switch(data.event_type){
          case'position.updated':
          case'signal.received':
          case'risk.check_passed':
          case'risk.check_failed':
          case'error.occurred':
            refresh();
            break;
        }
      }catch(error){
        console.error('WebSocket message error:',error);
      }
    };
    
    ws.onopen=()=>{
      console.log('WebSocket connected');
      // Send heartbeat every 30 seconds
      setInterval(()=>{
        try{
          if(ws.readyState===WebSocket.OPEN){
            ws.send('ping');
          }
        }catch(error){
          console.error('WebSocket heartbeat error:',error);
        }
      },30000);
    };
    
    ws.onerror=(error)=>{
      console.error('WebSocket error:',error);
    };
    
    ws.onclose=()=>{
      console.log('WebSocket disconnected');
      // Attempt to reconnect after 5 seconds
      setTimeout(connectWS,5000);
    };
    
  }catch(error){
    console.error('Failed to connect WebSocket:',error);
  }
}

window.addEventListener('DOMContentLoaded',async()=>{
  initCharts();
  await refresh();
  connectWS();
  
  // Refresh every 5 seconds
  setInterval(refresh,5000);
  
  // Reset signal count every minute
  setInterval(()=>{
    signalCount=0;
    lastSignalTime=Date.now();
  },60000);
})