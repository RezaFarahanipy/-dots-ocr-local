const $ = (id) => document.getElementById(id);
let activeJob = null;
const labels = {queued:"در صف",processing:"در حال پردازش",completed:"تکمیل شد",failed:"ناموفق"};
async function api(url, opts){const r=await fetch(url,opts);if(!r.ok){let d={};try{d=await r.json()}catch{};throw new Error(d.detail||"خطا در ارتباط با سرور")}return r.json()}
async function checkHealth(){
  try{
    const d=await api("/api/health");
    const m=d.model;
    $("systemStatus").innerHTML = `<i style="background:${m.model_exists?'#19a879':'#e4a23d'}"></i>${m.model_exists?'مدل در دسترس':'وزن‌های مدل نصب نشده'}`;
  }catch{$("systemStatus").innerHTML='<i style="background:#d9534f"></i>سرور در دسترس نیست'}
}
function showFile(file){
  if(!file)return;
  $("selectedFile").classList.remove("hidden");
  $("selectedFile").innerHTML=`<span>📄 ${file.name}</span><span>${(file.size/1024/1024).toFixed(2)} MB</span>`;
  upload(file);
}
async function upload(file){
  $("jobPanel").classList.remove("hidden");$("jobError").classList.add("hidden");
  $("jobName").textContent=file.name;$("jobState").textContent="در حال ارسال فایل";$("jobPercent").textContent="0%";$("progressBar").style.width="0%";
  const fd=new FormData();fd.append("file",file);
  try{
    const d=await api("/api/documents",{method:"POST",body:fd});activeJob=d.id;pollJob(d.id);
  }catch(e){$("jobError").textContent=e.message;$("jobError").classList.remove("hidden")}
}
async function pollJob(id){
  try{
    const d=await api(`/api/jobs/${id}`);
    $("jobState").textContent=labels[d.status]||d.status;$("jobPercent").textContent=`${d.progress||0}%`;$("progressBar").style.width=`${d.progress||0}%`;
    if(d.status==="completed"){
      $("resultSection").classList.remove("hidden");$("resultText").textContent=d.result?.text||"متنی برگردانده نشد.";
      $("mdLink").href=`/api/jobs/${id}/export/md`;$("jsonLink").href=`/api/jobs/${id}/export/json`;
      loadHistory();return;
    }
    if(d.status==="failed"){$("jobError").textContent=d.error||"پردازش ناموفق بود.";$("jobError").classList.remove("hidden");loadHistory();return}
    setTimeout(()=>pollJob(id),2500);
  }catch(e){$("jobError").textContent=e.message;$("jobError").classList.remove("hidden")}
}
async function loadHistory(){
  try{
    const rows=await api("/api/jobs");
    $("historyList").innerHTML=rows.length?rows.map(x=>`<div class="history-item"><div>${x.filename}<small>${new Date(x.created_at).toLocaleString("fa-IR")}</small></div><span class="state ${x.status}">${labels[x.status]||x.status}</span></div>`).join(""):'<div class="empty">هنوز سندی پردازش نشده است.</div>';
  }catch{}
}
$("fileInput").addEventListener("change",e=>showFile(e.target.files[0]));
const dz=$("dropzone");
["dragenter","dragover"].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.add("drag")}));
["dragleave","drop"].forEach(ev=>dz.addEventListener(ev,e=>{e.preventDefault();dz.classList.remove("drag")}));
dz.addEventListener("drop",e=>showFile(e.dataTransfer.files[0]));
$("copyBtn").addEventListener("click",async()=>{await navigator.clipboard.writeText($("resultText").textContent);$("copyBtn").textContent="کپی شد"});
checkHealth();loadHistory();
