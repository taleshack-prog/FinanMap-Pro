/**
 * Tela Robôs & Algoritmo Genético — diferencial principal do FinanMap Pro
 * Animações com Reanimated, evolução em tempo real, laboratório de cruzamento
 */

import React, { useState, useEffect, useRef, useCallback } from 'react';
import {
  View, Text, ScrollView, TouchableOpacity,
  StyleSheet, Dimensions, Alert,
} from 'react-native';
import Animated, {
  useSharedValue, useAnimatedStyle,
  withSpring, withTiming, withSequence, withRepeat,
  FadeInUp, FadeInRight, ZoomIn,
  interpolate, Easing,
} from 'react-native-reanimated';
import * as Haptics from 'expo-haptics';
import { LinearGradient } from 'expo-linear-gradient';

import { Colors, Typography, Spacing, Radii, Shadows } from '../theme';
import { Card, SectionHeader, Chip, Button, AllocBar, MetricCard } from '../components';
import { useStore, Robot } from '../store';
import ApiService from '../services/api';

const { width: W } = Dimensions.get('window');

// ── GA Engine (local — espelha o backend) ─────────────────────────────────────

const GENES  = ['renda_fixa','renda_var','internacional','cripto'] as const;
const RET    = { renda_fixa:.105, renda_var:.12, internacional:.14, cripto:.45 };
const VOL    = { renda_fixa:.03,  renda_var:.20, internacional:.15, cripto:.70 };
const RF     = .105/12;
const EMOJIS = ['🤖','🦾','🧬','⚡','🔬','🧪','🛸','💎','🔮','🌀','🦅','🐉','🎯','🔥','🧠','🌊'];
const PFXS   = ['Alpha','Beta','Gamma','Delta','Sigma','Omega','Nova','Zeta','Titan','Nexus','Apex','Flux'];

function rnd(a:number,b:number){ return Math.random()*(b-a)+a; }
function rndI(a:number,b:number){ return Math.floor(rnd(a,b+1)); }

function normGenes(g: Record<string,number>) {
  const t = GENES.reduce((s,k)=>s+(g[k]||0),0);
  if(!t) return g;
  const r: Record<string,number> = {};
  GENES.forEach(k=>r[k]=Math.max(0,Math.round((g[k]||0)/t*1000)/10));
  return r;
}

function calcFit(genes: Record<string,number>, bsPenalty=0.5) {
  const mu  = GENES.reduce((s,k)=>s+(genes[k]||0)/100*RET[k],0);
  const sig = Math.sqrt(GENES.reduce((s,k)=>s+Math.pow((genes[k]||0)/100,2)*Math.pow(VOL[k],2),0))||.001;
  let sort  = (mu - RF*12) / (sig*.75);
  if((genes.cripto||0)>40) sort -= bsPenalty;
  if((genes.cripto||0)>60) sort -= bsPenalty*1.5;
  return Math.max(0, Math.round(sort*1000)/1000);
}

function calcCAGR(g: Record<string,number>) {
  return Math.round(GENES.reduce((s,k)=>s+(g[k]||0)/100*RET[k],0)*1000)/10;
}

function makeRobot(i:number, genes?:Record<string,number>, gen=0): Robot {
  if(!genes){
    const w = GENES.map(()=>rnd(5,50));
    const t = w.reduce((a,b)=>a+b,0);
    genes={};
    GENES.forEach((k,j)=>genes![k]=Math.round(w[j]/t*1000)/10);
  }
  genes = normGenes(genes);
  return {
    id:i, emoji:EMOJIS[i%EMOJIS.length], name:PFXS[i%PFXS.length]+'-'+(1000+i),
    strain:'v'+rndI(1,999)+'.'+rndI(0,9), genes, gen,
    fit:calcFit(genes), cagr:calcCAGR(genes),
    status: i<3?'elite': i<5?'mutante': i>6?'extinto':'normal',
  };
}

// ── RobotCard Component ────────────────────────────────────────────────────────

function RobotCard({ robot, onPress, selected, index }:
  { robot:Robot; onPress:()=>void; selected:boolean; index:number }) {

  const scale = useSharedValue(1);
  const glow  = useSharedValue(0);

  useEffect(() => {
    if(robot.status==='elite'){
      glow.value = withRepeat(withSequence(
        withTiming(1,{duration:1200,easing:Easing.inOut(Easing.sine)}),
        withTiming(0,{duration:1200,easing:Easing.inOut(Easing.sine)}),
      ), -1);
    }
  }, [robot.status]);

  const aStyle = useAnimatedStyle(()=>({
    transform:[{scale:scale.value}],
    shadowOpacity: interpolate(glow.value,[0,1],[0.06,0.25]),
    shadowRadius:  interpolate(glow.value,[0,1],[4,18]),
  }));

  const statusColors = {
    elite:   { bg:Colors.greenLight,  border:Colors.green,  label:'élite',   lc:'#065F46' },
    mutante: { bg:Colors.amberLight,  border:Colors.amber,  label:'mutante', lc:'#92400E' },
    extinto: { bg:Colors.redLight,    border:Colors.red,    label:'extinto', lc:'#991B1B' },
    normal:  { bg:Colors.purpleLight, border:Colors.purple, label:'',        lc:'' },
  };
  const sc = statusColors[robot.status] || statusColors.normal;
  const geneColors = Colors.gene as Record<string,string>;

  return (
    <Animated.View
      entering={FadeInUp.delay(index*60).duration(350)}
      style={[aStyle, { shadowColor: robot.status==='elite'?Colors.green:Colors.purple }]}
    >
      <TouchableOpacity
        onPress={()=>{ Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light); onPress(); scale.value=withSequence(withSpring(0.96),withSpring(1)); }}
        activeOpacity={1}
        style={[styles.robotCard,
          { borderLeftColor: sc.border },
          selected && { borderColor:Colors.purple, borderWidth:2, backgroundColor:Colors.purpleLight },
        ]}
      >
        {/* Avatar + badge */}
        <View style={{ flexDirection:'row', alignItems:'flex-start', justifyContent:'space-between', marginBottom:Spacing.xs }}>
          <View style={[styles.robotAvatar, { backgroundColor: sc.bg }]}>
            <Text style={{ fontSize: 22 }}>{robot.emoji}</Text>
          </View>
          {robot.status !== 'normal' && (
            <View style={[styles.statusBadge, { backgroundColor: sc.bg }]}>
              <Text style={[styles.statusText, { color: sc.lc }]}>{sc.label}</Text>
            </View>
          )}
        </View>

        <Text style={styles.robotName}>{robot.name}</Text>
        <Text style={styles.robotStrain}>{robot.strain}</Text>

        {/* Fitness bar */}
        <View style={styles.fitBarBg}>
          <View style={[styles.fitBarFill, {
            width:`${Math.min(100, robot.fit*45)}%`,
            backgroundColor: robot.status==='elite'?Colors.green: robot.status==='mutante'?Colors.amber:Colors.purple,
          }]}/>
        </View>

        <View style={styles.robotStats}>
          <Text style={styles.robotStatLabel}>Sortino</Text>
          <Text style={styles.robotStatVal}>{robot.fit.toFixed(3)}</Text>
        </View>
        <View style={styles.robotStats}>
          <Text style={styles.robotStatLabel}>CAGR</Text>
          <Text style={styles.robotStatVal}>{robot.cagr}%</Text>
        </View>

        {/* DNA strip */}
        <View style={{ flexDirection:'row', height:5, borderRadius:2.5, overflow:'hidden', gap:1, marginTop:Spacing.xs }}>
          {GENES.map(k=>(
            <View key={k} style={{ flex:robot.genes[k]||0, backgroundColor:geneColors[k]||Colors.purple }}/>
          ))}
        </View>

      </TouchableOpacity>
    </Animated.View>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function RobotsScreen() {
  const [robots,    setRobots_]  = useState<Robot[]>([]);
  const [selected,  setSelected] = useState<number[]>([]);
  const [running,   setRunning]  = useState(false);
  const [gen,       setGen]      = useState(0);
  const [history,   setHistory]  = useState<{best:number;avg:number}[]>([]);
  const [bestRobot, setBestRobot]= useState<Robot|null>(null);
  const [child,     setChild]    = useState<Robot|null>(null);
  const [detail,    setDetail]   = useState<Robot|null>(null);
  const [mutPenalty,setMutPenalty]=useState(15);
  const [bsPenalty, setBsPenalty]=useState(0.5);

  const intervalRef = useRef<any>(null);
  const storeSetRobots = useStore(s => s.setRobots);
  const user = useStore(s => s.user);

  const MAX_GEN = 50;

  // Semente Kelly baseada no perfil do usuário
  const SEEDS: Record<string,Record<string,number>> = {
    conservador:        { renda_fixa:70, renda_var:20, internacional:10, cripto:0  },
    moderado:           { renda_fixa:50, renda_var:30, internacional:15, cripto:5  },
    moderado_agressivo: { renda_fixa:35, renda_var:30, internacional:15, cripto:20 },
    agressivo:          { renda_fixa:20, renda_var:30, internacional:15, cripto:35 },
  };

  useEffect(()=>{ initRobots(); return ()=>stop(); },[]);

  function initRobots(){
    const seed = SEEDS[user?.perfil||'moderado_agressivo'];
    const pop: Robot[] = [];
    for(let i=0;i<8;i++){
      pop.push(makeRobot(i, i===0?{...seed}:undefined));
    }
    pop.sort((a,b)=>b.fit-a.fit);
    setRobots_(pop);
    setBestRobot(pop[0]);
    storeSetRobots(pop);
    setGen(0); setHistory([]); setSelected([]); setChild(null);
  }

  function gaStep(bots: Robot[], penalty: number, bsPen: number) {
    bots.sort((a,b)=>b.fit-a.fit);
    const elite = bots.slice(0,2).map(r=>({...r, status:'elite' as const}));
    const nova: Robot[] = [...elite];
    while(nova.length<8){
      const p1 = bots[rndI(0,Math.min(3,bots.length-1))];
      const p2 = bots[rndI(0,Math.min(3,bots.length-1))];
      const g: Record<string,number> = {};
      GENES.forEach(k=>{
        let v = Math.random()<.5?(p1.genes[k]||0):(p2.genes[k]||0);
        if(Math.random()<penalty/100) v = Math.max(0, v+rnd(-12,12));
        g[k]=v;
      });
      const normed = normGenes(g);
      const fit = calcFit(normed, bsPen);
      const idx = nova.length;
      nova.push({
        id:idx, emoji:EMOJIS[rndI(0,EMOJIS.length-1)],
        name:PFXS[rndI(0,PFXS.length-1)]+'-'+rndI(1000,9999),
        strain:'v'+rndI(1,999)+'.'+rndI(0,9),
        genes:normed, fit, cagr:calcCAGR(normed),
        status: idx<3?'elite': Math.random()<.12?'mutante': idx>6?'extinto':'normal',
        gen: gen+1,
      });
    }
    return nova.slice(0,8);
  }

  const start = useCallback(()=>{
    if(running){ stop(); return; }
    if(gen>=MAX_GEN){ Haptics.notificationAsync(Haptics.NotificationFeedbackType.Warning); return; }
    setRunning(true);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
    let currentRobots = [...robots];
    let currentGen    = gen;
    intervalRef.current = setInterval(()=>{
      if(currentGen>=MAX_GEN){ stop(); return; }
      currentGen++;
      currentRobots = gaStep(currentRobots, mutPenalty, bsPenalty);
      const best = currentRobots[0];
      const avg  = Math.round(currentRobots.reduce((s,r)=>s+r.fit,0)/currentRobots.length*1000)/1000;
      setRobots_(currentRobots);
      setBestRobot(best);
      storeSetRobots(currentRobots);
      setGen(currentGen);
      setHistory(h=>[...h, { best:best.fit, avg }].slice(-50));
      if(currentGen%10===0) Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Light);
    }, 220);
  },[robots, gen, running, mutPenalty, bsPenalty]);

  function stop(){
    clearInterval(intervalRef.current);
    setRunning(false);
  }

  function reset(){
    stop();
    initRobots();
    setGen(0); setHistory([]);
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium);
  }

  function selectRobot(i:number){
    setSelected(sel=>{
      if(sel.includes(i)) return sel.filter(x=>x!==i);
      if(sel.length<2)    return [...sel, i];
      return [i];
    });
    setDetail(robots[i]);
  }

  function crossRobots(){
    if(selected.length<2) return;
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success);
    const p1=robots[selected[0]], p2=robots[selected[1]];
    const g: Record<string,number>={};
    GENES.forEach(k=>{
      let v = Math.random()<.5?(p1.genes[k]||0):(p2.genes[k]||0);
      if(Math.random()<mutPenalty/100) v=Math.max(0,v+rnd(-15,15));
      g[k]=v;
    });
    const normed=normGenes(g);
    const fit=calcFit(normed,bsPenalty);
    const isMutant=fit>Math.max(p1.fit,p2.fit)*1.04;
    const child:Robot={
      id:robots.length, emoji:EMOJIS[rndI(0,EMOJIS.length-1)],
      name:PFXS[rndI(0,PFXS.length-1)]+'-'+rndI(1000,9999),
      strain:'v'+(gen+1)+'.0', genes:normed, fit, cagr:calcCAGR(normed),
      status:isMutant?'mutante':'normal', gen:gen+1,
    };
    setChild(child);
    if(isMutant){
      Alert.alert('🧬 Nova Strain Detectada!', `${child.name} superou os pais em ${((fit/Math.max(p1.fit,p2.fit)-1)*100).toFixed(1)}%!\nSortino: ${fit.toFixed(3)}`,
        [{text:'Adicionar à população', onPress:()=>{
          setRobots_(r=>[...r, child]);
          storeSetRobots([...robots, child]);
        }}, {text:'Descartar'}]);
    }
  }

  const best = bestRobot || robots[0];
  const isNova = history.length>5 && history[history.length-1]?.best > (history[history.length-6]?.best||0)*1.03;
  const geneColors = Colors.gene as Record<string,string>;

  return (
    <ScrollView style={styles.container} showsVerticalScrollIndicator={false}>

      {/* ── Métricas topo ── */}
      <View style={styles.metricsRow}>
        <MetricCard label="Robôs ativos"  value={String(robots.filter(r=>r.status!=='extinto').length)} accent={Colors.purple} style={{ flex:1 }}/>
        <MetricCard label="Melhor Sortino" value={best?.fit.toFixed(3)||'—'} accent={Colors.green} style={{ flex:1 }}/>
        <MetricCard label="Geração"       value={String(gen)+'/'+MAX_GEN}   accent={Colors.amber} style={{ flex:1 }}/>
        <MetricCard label="Melhor CAGR"   value={(best?.cagr||0)+'%'}       accent={Colors.blue}  style={{ flex:1 }}/>
      </View>

      {/* ── Grade de Robôs ── */}
      <View style={styles.section}>
        <SectionHeader title="População de Robôs" sub="Cada robô é uma estratégia de alocação evoluída · toque para inspecionar" />
        <View style={styles.robotsGrid}>
          {robots.map((r,i)=>(
            <View key={r.id+'-'+r.strain} style={{ width:(W-Spacing.xl*2-Spacing.sm)/2 }}>
              <RobotCard robot={r} index={i} onPress={()=>selectRobot(i)} selected={selected.includes(i)}/>
            </View>
          ))}
        </View>
      </View>

      {/* ── Controles GA ── */}
      <View style={styles.section}>
        <Card>
          <SectionHeader title="Arena do Algoritmo Genético" sub="Fitness = Sortino pós-Monte Carlo · black swans incluídos" />

          {/* Status */}
          <View style={styles.gaStatus}>
            <View style={{ flexDirection:'row', alignItems:'center', gap:Spacing.sm }}>
              <View style={[styles.gaStatusDot, { backgroundColor: running?Colors.green: gen>=MAX_GEN?Colors.purple:Colors.text4 }]}/>
              <Text style={styles.gaStatusText}>
                {running?'Evoluindo população...': gen>=MAX_GEN?'Evolução concluída! 🏆': gen>0?'Pausado na geração '+gen:'Aguardando início'}
              </Text>
            </View>
            {isNova && <Chip label="Nova strain 🧬" bg={Colors.amberLight} color="#92400E"/>}
          </View>

          {/* Sliders */}
          <View style={styles.sliderGroup}>
            <Text style={styles.sliderTitle}>Taxa de mutação: <Text style={{ color:Colors.purple }}>{mutPenalty}%</Text></Text>
            <View style={styles.pillRow}>
              {[5,10,15,25,35,50].map(v=>(
                <TouchableOpacity key={v} onPress={()=>{ setMutPenalty(v); Haptics.selectionAsync(); }}
                  style={[styles.pill, mutPenalty===v && styles.pillActive]}>
                  <Text style={[styles.pillText, mutPenalty===v && { color:Colors.purple }]}>{v}%</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          <View style={styles.sliderGroup}>
            <Text style={styles.sliderTitle}>Penalidade black swan: <Text style={{ color:Colors.amber }}>{bsPenalty.toFixed(1)}×</Text></Text>
            <View style={styles.pillRow}>
              {[0,0.3,0.5,1.0,1.5,2.0].map(v=>(
                <TouchableOpacity key={v} onPress={()=>{ setBsPenalty(v); Haptics.selectionAsync(); }}
                  style={[styles.pill, bsPenalty===v && styles.pillActive]}>
                  <Text style={[styles.pillText, bsPenalty===v && { color:Colors.amber }]}>{v}×</Text>
                </TouchableOpacity>
              ))}
            </View>
          </View>

          {/* Métricas GA */}
          <View style={styles.gaMetrics}>
            {[
              { l:'Sortino', v:best?.fit.toFixed(3)||'—', c:Colors.purple },
              { l:'CAGR',    v:(best?.cagr||0)+'%',       c:Colors.green  },
              { l:'Div.',    v:Math.round(robots.reduce((s,r)=>s+(r.genes['renda_var']||0),0)/Math.max(robots.length,1))+'%RV', c:Colors.amber },
              { l:'Strain',  v:isNova?'Nova!':'Estável',   c:isNova?Colors.green:Colors.text3 },
            ].map(m=>(
              <View key={m.l} style={styles.gaMet}>
                <Text style={styles.gaMetL}>{m.l}</Text>
                <Text style={[styles.gaMetV, { color:m.c }]}>{m.v}</Text>
              </View>
            ))}
          </View>

          {/* Botões */}
          <View style={styles.gaButtons}>
            <TouchableOpacity onPress={start} style={[styles.gaBtn, styles.gaBtnPrimary, gen>=MAX_GEN && { opacity:.5 }]} disabled={gen>=MAX_GEN}>
              <Text style={styles.gaBtnText}>{running?'⏸ Pausar':'▶ Iniciar'}</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={()=>{ if(!running){ const r=gaStep([...robots],mutPenalty,bsPenalty); setRobots_(r); setGen(g=>g+1); }}} style={styles.gaBtn} disabled={running||gen>=MAX_GEN}>
              <Text style={[styles.gaBtnText, { color:Colors.text }]}>+1 Geração</Text>
            </TouchableOpacity>
            <TouchableOpacity onPress={reset} style={styles.gaBtn}>
              <Text style={[styles.gaBtnText, { color:Colors.text2 }]}>↺ Reset</Text>
            </TouchableOpacity>
          </View>
        </Card>
      </View>

      {/* ── Mini gráfico de fitness ── */}
      {history.length > 1 && (
        <View style={styles.section}>
          <Card>
            <SectionHeader title="Evolução do fitness" sub="Melhor robô vs. média da população" />
            <View style={{ height:80, flexDirection:'row', alignItems:'flex-end', gap:2, marginTop:Spacing.sm }}>
              {history.slice(-40).map((h,i,arr)=>{
                const maxFit=Math.max(...arr.map(x=>x.best))||1;
                const hBest=Math.max(4,(h.best/maxFit)*70);
                const hAvg =Math.max(2,(h.avg /maxFit)*70);
                return(
                  <View key={i} style={{ flex:1, alignItems:'center', justifyContent:'flex-end', gap:1 }}>
                    <View style={{ width:'100%', height:hAvg,  backgroundColor:Colors.text4,   borderRadius:1.5 }}/>
                    <View style={{ width:'100%', height:Math.max(0,hBest-hAvg), backgroundColor:Colors.purple, borderRadius:1.5 }}/>
                  </View>
                );
              })}
            </View>
            <View style={{ flexDirection:'row', gap:Spacing.lg, marginTop:Spacing.sm }}>
              <View style={{ flexDirection:'row', alignItems:'center', gap:4 }}>
                <View style={{ width:10, height:10, borderRadius:2, backgroundColor:Colors.purple }}/>
                <Text style={{ fontSize:Typography.xs, color:Colors.text2 }}>Melhor</Text>
              </View>
              <View style={{ flexDirection:'row', alignItems:'center', gap:4 }}>
                <View style={{ width:10, height:10, borderRadius:2, backgroundColor:Colors.text4 }}/>
                <Text style={{ fontSize:Typography.xs, color:Colors.text2 }}>Média</Text>
              </View>
            </View>
          </Card>
        </View>
      )}

      {/* ── Laboratório de Cruzamento ── */}
      <View style={styles.section}>
        <SectionHeader title="Laboratório de Cruzamento" sub="Selecione 2 robôs na grade · crossover uniforme + mutação gaussiana" />
        <Card>
          <View style={styles.crossRow}>
            {/* Pai 1 */}
            <View style={styles.crossBox}>
              <Text style={styles.crossBoxLabel}>Pai 1</Text>
              {selected.length>=1 ? (
                <>
                  <Text style={{ fontSize:28, marginVertical:4 }}>{robots[selected[0]]?.emoji}</Text>
                  <Text style={styles.crossBoxName}>{robots[selected[0]]?.name}</Text>
                  <View style={{ flexDirection:'row', flexWrap:'wrap', gap:2, justifyContent:'center', marginTop:4 }}>
                    {GENES.map(k=>(
                      <View key={k} style={[styles.dnaGene, { backgroundColor:geneColors[k]+'22' }]}>
                        <Text style={[styles.dnaText, { color:geneColors[k] }]}>{k.slice(0,2).toUpperCase()}{Math.round(robots[selected[0]]?.genes[k]||0)}%</Text>
                      </View>
                    ))}
                  </View>
                </>
              ) : <Text style={styles.crossPlaceholder}>selecione</Text>}
            </View>

            <View style={{ alignItems:'center', gap:Spacing.sm }}>
              <Text style={styles.crossSym}>×</Text>
              <TouchableOpacity onPress={crossRobots} disabled={selected.length<2}
                style={[styles.crossBtn, selected.length<2 && { opacity:.35 }]}>
                <Text style={styles.crossBtnText}>Cruzar</Text>
              </TouchableOpacity>
              <Text style={styles.crossSym}>→</Text>
            </View>

            {/* Pai 2 */}
            <View style={styles.crossBox}>
              <Text style={styles.crossBoxLabel}>Pai 2</Text>
              {selected.length>=2 ? (
                <>
                  <Text style={{ fontSize:28, marginVertical:4 }}>{robots[selected[1]]?.emoji}</Text>
                  <Text style={styles.crossBoxName}>{robots[selected[1]]?.name}</Text>
                  <View style={{ flexDirection:'row', flexWrap:'wrap', gap:2, justifyContent:'center', marginTop:4 }}>
                    {GENES.map(k=>(
                      <View key={k} style={[styles.dnaGene, { backgroundColor:geneColors[k]+'22' }]}>
                        <Text style={[styles.dnaText, { color:geneColors[k] }]}>{k.slice(0,2).toUpperCase()}{Math.round(robots[selected[1]]?.genes[k]||0)}%</Text>
                      </View>
                    ))}
                  </View>
                </>
              ) : <Text style={styles.crossPlaceholder}>selecione</Text>}
            </View>

            {/* Filho */}
            <View style={[styles.crossBox, { borderColor:Colors.purple, borderWidth:1.5 }]}>
              <Text style={styles.crossBoxLabel}>Filho</Text>
              {child ? (
                <Animated.View entering={ZoomIn.duration(300)}>
                  <Text style={{ fontSize:28, marginVertical:4 }}>{child.emoji}</Text>
                  <Text style={styles.crossBoxName}>{child.name}</Text>
                  <Text style={{ fontSize:Typography.xs, color:Colors.purple, marginTop:2, fontWeight:Typography.bold }}>
                    Sortino {child.fit.toFixed(3)}
                  </Text>
                  {child.status==='mutante' && (
                    <View style={[styles.statusBadge, { backgroundColor:Colors.amberLight, marginTop:4 }]}>
                      <Text style={{ fontSize:9, color:'#92400E', fontWeight:Typography.bold }}>🧬 nova strain!</Text>
                    </View>
                  )}
                </Animated.View>
              ) : <Text style={styles.crossPlaceholder}>aguardando</Text>}
            </View>
          </View>
        </Card>
      </View>

      {/* ── Detalhe do robô ── */}
      {detail && (
        <Animated.View entering={FadeInUp.duration(350)} style={styles.section}>
          <Card>
            <View style={{ flexDirection:'row', alignItems:'center', gap:Spacing.md, marginBottom:Spacing.lg }}>
              <Text style={{ fontSize:36 }}>{detail.emoji}</Text>
              <View style={{ flex:1 }}>
                <Text style={styles.detailName}>{detail.name}</Text>
                <Text style={styles.detailStrain}>Strain {detail.strain} · Geração {detail.gen}</Text>
              </View>
              <Chip
                label={detail.status}
                bg={detail.status==='elite'?Colors.greenLight: detail.status==='mutante'?Colors.amberLight:Colors.purpleLight}
                color={detail.status==='elite'?'#065F46': detail.status==='mutante'?'#92400E':Colors.purpleDark}
              />
            </View>

            <Text style={[styles.sliderTitle, { marginBottom:Spacing.md }]}>Genoma — Alocação</Text>
            {GENES.map(k=>{
              const pct=Math.round(detail.genes[k]||0);
              return(
                <View key={k} style={styles.allocRow}>
                  <View style={[styles.allocDot, { backgroundColor:geneColors[k] }]}/>
                  <Text style={styles.allocName}>{k.replace('_',' ')}</Text>
                  <View style={styles.allocTrack}>
                    <View style={{ width:`${pct}%`, height:4, borderRadius:2, backgroundColor:geneColors[k] }}/>
                  </View>
                  <Text style={styles.allocPct}>{pct}%</Text>
                </View>
              );
            })}

            <View style={styles.detailStats}>
              {[
                { l:'Sortino', v:detail.fit.toFixed(3),       c:Colors.purple },
                { l:'CAGR',    v:detail.cagr+'%',             c:Colors.green  },
                { l:'Sharpe',  v:(detail.fit*0.82).toFixed(3),c:Colors.blue   },
                { l:'Risco',   v:(detail.genes['cripto']||0)>30?'Alto':'Moderado', c:(detail.genes['cripto']||0)>30?Colors.amber:Colors.green },
              ].map(s=>(
                <View key={s.l} style={styles.detailStat}>
                  <Text style={styles.detailStatL}>{s.l}</Text>
                  <Text style={[styles.detailStatV, { color:s.c }]}>{s.v}</Text>
                </View>
              ))}
            </View>
          </Card>
        </Animated.View>
      )}

      {/* ── Leaderboard ── */}
      <View style={[styles.section, { paddingBottom:Spacing.xxxl*2 }]}>
        <Card>
          <SectionHeader title="Leaderboard — Top Robôs" sub="Ranking por Sortino Ratio" />
          {[...robots].sort((a,b)=>b.fit-a.fit).slice(0,5).map((r,i)=>(
            <Animated.View key={r.id} entering={FadeInRight.delay(i*80).duration(300)}>
              <TouchableOpacity onPress={()=>setDetail(r)} style={styles.lbRow}>
                <Text style={[styles.lbRank, i===0&&{color:Colors.amber}, i===1&&{color:Colors.text3}, i===2&&{color:'#CD7F32'}]}>
                  #{i+1}
                </Text>
                <Text style={{ fontSize:20 }}>{r.emoji}</Text>
                <View style={{ flex:1 }}>
                  <Text style={styles.lbName}>{r.name}</Text>
                  <Text style={styles.lbSub}>{r.strain} · CAGR {r.cagr}%</Text>
                </View>
                <Text style={styles.lbFit}>{r.fit.toFixed(3)}</Text>
              </TouchableOpacity>
            </Animated.View>
          ))}
        </Card>
      </View>

    </ScrollView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container:       { flex:1, backgroundColor:Colors.bg },
  section:         { paddingHorizontal:Spacing.xl, marginBottom:Spacing.lg },
  metricsRow:      { flexDirection:'row', gap:Spacing.sm, paddingHorizontal:Spacing.xl, paddingTop:Spacing.lg, paddingBottom:Spacing.md },

  robotsGrid:      { flexDirection:'row', flexWrap:'wrap', gap:Spacing.sm },
  robotCard:       { backgroundColor:Colors.surface, borderRadius:Radii.lg, padding:Spacing.md, borderWidth:1, borderColor:Colors.border, borderLeftWidth:3, ...Shadows.sm },
  robotAvatar:     { width:42, height:42, borderRadius:Radii.md, alignItems:'center', justifyContent:'center' },
  statusBadge:     { paddingHorizontal:6, paddingVertical:2, borderRadius:Radii.full },
  statusText:      { fontSize:9, fontWeight:Typography.bold },
  robotName:       { fontSize:Typography.sm, fontWeight:Typography.bold, color:Colors.text, marginBottom:1 },
  robotStrain:     { fontSize:Typography.xs, color:Colors.text3, marginBottom:Spacing.sm },
  fitBarBg:        { height:3, backgroundColor:Colors.bg, borderRadius:1.5, marginBottom:5 },
  fitBarFill:      { height:3, borderRadius:1.5 },
  robotStats:      { flexDirection:'row', justifyContent:'space-between', marginBottom:2 },
  robotStatLabel:  { fontSize:9, color:Colors.text3 },
  robotStatVal:    { fontSize:9, fontWeight:Typography.bold, color:Colors.text2 },

  gaStatus:        { flexDirection:'row', alignItems:'center', justifyContent:'space-between', backgroundColor:Colors.bg, borderRadius:Radii.sm, padding:Spacing.sm, marginBottom:Spacing.md },
  gaStatusDot:     { width:7, height:7, borderRadius:3.5 },
  gaStatusText:    { fontSize:Typography.sm, color:Colors.text2 },

  sliderGroup:     { marginBottom:Spacing.md },
  sliderTitle:     { fontSize:Typography.sm, fontWeight:Typography.semibold, color:Colors.text2, marginBottom:Spacing.xs },
  pillRow:         { flexDirection:'row', flexWrap:'wrap', gap:Spacing.xs },
  pill:            { paddingHorizontal:Spacing.sm, paddingVertical:Spacing.xs, borderRadius:Radii.full, borderWidth:1, borderColor:Colors.border, backgroundColor:Colors.bg },
  pillActive:      { borderColor:Colors.purple, backgroundColor:Colors.purpleLight },
  pillText:        { fontSize:Typography.xs, color:Colors.text2 },

  gaMetrics:       { flexDirection:'row', gap:Spacing.xs, marginBottom:Spacing.md },
  gaMet:           { flex:1, backgroundColor:Colors.bg, borderRadius:Radii.sm, padding:Spacing.sm },
  gaMetL:          { fontSize:9, color:Colors.text3, textTransform:'uppercase', letterSpacing:.4, marginBottom:3 },
  gaMetV:          { fontSize:Typography.base, fontWeight:Typography.black },

  gaButtons:       { flexDirection:'row', gap:Spacing.sm },
  gaBtn:           { flex:1, paddingVertical:Spacing.sm, borderRadius:Radii.sm, alignItems:'center', borderWidth:1, borderColor:Colors.border, backgroundColor:Colors.surface },
  gaBtnPrimary:    { backgroundColor:Colors.purple, borderColor:Colors.purple },
  gaBtnText:       { fontSize:Typography.sm, fontWeight:Typography.bold, color:'white' },

  crossRow:        { flexDirection:'row', alignItems:'center', gap:Spacing.xs },
  crossBox:        { flex:1, backgroundColor:Colors.bg, borderRadius:Radii.md, padding:Spacing.sm, alignItems:'center', borderWidth:1, borderColor:Colors.border },
  crossBoxLabel:   { fontSize:Typography.xs, color:Colors.text3, marginBottom:2 },
  crossBoxName:    { fontSize:9, fontWeight:Typography.bold, color:Colors.text, textAlign:'center' },
  crossPlaceholder:{ fontSize:Typography.xs, color:Colors.text3, marginTop:Spacing.xl },
  crossSym:        { fontSize:18, color:Colors.text4 },
  crossBtn:        { paddingHorizontal:Spacing.sm, paddingVertical:Spacing.xs, borderRadius:Radii.full, backgroundColor:Colors.purple },
  crossBtnText:    { fontSize:Typography.xs, fontWeight:Typography.bold, color:'white' },
  dnaGene:         { paddingHorizontal:4, paddingVertical:2, borderRadius:4 },
  dnaText:         { fontSize:8, fontWeight:Typography.bold },

  allocRow:        { flexDirection:'row', alignItems:'center', gap:Spacing.sm, marginBottom:Spacing.sm },
  allocDot:        { width:10, height:10, borderRadius:3 },
  allocName:       { flex:1, fontSize:Typography.sm, color:Colors.text2 },
  allocTrack:      { width:80, height:4, backgroundColor:Colors.bg, borderRadius:2 },
  allocPct:        { fontSize:Typography.sm, fontWeight:Typography.bold, minWidth:32, textAlign:'right' },

  detailName:      { fontSize:Typography.md, fontWeight:Typography.black, color:Colors.text },
  detailStrain:    { fontSize:Typography.xs, color:Colors.text3, marginTop:2 },
  detailStats:     { flexDirection:'row', flexWrap:'wrap', gap:Spacing.sm, marginTop:Spacing.lg },
  detailStat:      { width:(W-Spacing.xl*2-Spacing.lg*2-Spacing.sm)/2, backgroundColor:Colors.bg, borderRadius:Radii.sm, padding:Spacing.sm },
  detailStatL:     { fontSize:9, color:Colors.text3, textTransform:'uppercase', letterSpacing:.4, marginBottom:3 },
  detailStatV:     { fontSize:Typography.lg, fontWeight:Typography.black },

  lbRow:           { flexDirection:'row', alignItems:'center', gap:Spacing.sm, paddingVertical:Spacing.sm, borderBottomWidth:1, borderColor:Colors.bg },
  lbRank:          { fontSize:Typography.base, fontWeight:Typography.black, color:Colors.text4, minWidth:24 },
  lbName:          { fontSize:Typography.sm, fontWeight:Typography.bold, color:Colors.text },
  lbSub:           { fontSize:Typography.xs, color:Colors.text3 },
  lbFit:           { fontSize:Typography.base, fontWeight:Typography.black, color:Colors.purple },
});
