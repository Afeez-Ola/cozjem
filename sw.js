const C="cozjem-v30";
self.addEventListener("install",e=>{e.waitUntil(caches.open(C).then(c=>c.addAll(["./","index.html","manifest.webmanifest","favicon.svg","icon-192.png"])));self.skipWaiting();});
self.addEventListener("activate",e=>{e.waitUntil(caches.keys().then(ks=>Promise.all(ks.filter(k=>k!==C).map(k=>caches.delete(k)))));self.clients.claim();});
self.addEventListener("fetch",e=>{const r=e.request; if(r.method!=="GET") return;
  e.respondWith(fetch(r,r.mode==="navigate"?{cache:"no-cache"}:{}).then(res=>{if(res.ok&&new URL(r.url).origin===location.origin){const cp=res.clone();caches.open(C).then(c=>c.put(r,cp));}return res;}).catch(()=>caches.match(r).then(m=>m||caches.match("index.html"))));});
// Promotion alerts
self.addEventListener("push",e=>{let d={};try{d=e.data?e.data.json():{};}catch(_){d={title:"CoZjem",body:e.data?e.data.text():""};}
  e.waitUntil(self.registration.showNotification(d.title||"CoZjem",{body:d.body||"",icon:"icon-192.png",badge:"icon-192.png",tag:d.tag||"cozjem-promos",renotify:true,data:{url:d.url||"/#offers"}}));});
self.addEventListener("notificationclick",e=>{e.notification.close();const url=new URL((e.notification.data&&e.notification.data.url)||"/#offers",self.location.origin).href;
  e.waitUntil(self.clients.matchAll({type:"window",includeUncontrolled:true}).then(cs=>{for(const c of cs){if(new URL(c.url).origin===self.location.origin&&"focus" in c){return c.navigate(url).then(w=>(w||c).focus()).catch(()=>c.focus());}}return self.clients.openWindow(url);}));});
