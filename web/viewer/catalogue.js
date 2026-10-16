// Versioned, independently authored catalogue for the embedded ComfyUI editors.
export const CATALOGUE_VERSION = 1;
export const ENGINE = '9242d189b6f8321a27c6f6a345aeb4e5991da569';
export const films = [
  ['vision250d', 'Vision3 250D', 'Daylight negative'],
  ['vision500t', 'Vision3 500T', 'Tungsten negative'],
  ['portra400', 'Portra 400', 'Soft portrait color'],
  ['gold200', 'Gold 200', 'Warm everyday color'],
  ['cinestill800t', 'CineStill 800T', 'Night and mixed light'],
  ['ektachromee100', 'Ektachrome E100', 'Direct-view slide film'],
  ['trix400', 'Tri-X 400', 'Black and white'],
  ['provia100f', 'Provia 100F', 'Balanced slide color'],
  ['velvia50', 'Velvia 50', 'Rich landscape color'],
  ['astia100f', 'Astia 100F', 'Soft slide color'],
  ['pro400h', 'Pro 400H', 'Gentle portrait color'],
  ['eterna500', 'Eterna 500', 'Soft cinema contrast'],
  ['ektar100', 'Ektar 100', 'Vivid, fine-grain negative'],
  ['superia400', 'Superia 400', 'Everyday negative color'],
  ['acros100', 'Acros 100', 'Fine monochrome texture'],
  ['doublex5222', 'Double-X', 'Classic cinema monochrome'],
  ["kodachrome25", "Kodachrome 25", "Color transparency"],
  ["kodachrome64", "Kodachrome 64", "Color transparency"],
  ["cinestill400d", "CineStill 400D", "Daylight negative"],
  ["ultramax400", "UltraMax 400", "Color negative"],
  ["pro160ns", "Pro 160NS", "Color negative"],
  ["reala500d", "Reala 500D", "Daylight cinema negative"],
  ["eternavivid500", "Eterna Vivid 500", "Tungsten cinema negative"],
  ["hp5plus400", "HP5 Plus 400", "Black and white"],
  ["tmax100", "T-Max 100", "Black and white"],
  ["delta3200", "Delta 3200", "Black and white"],
  ["instaxmini", "Instax Mini", "Instant color"],
  ["phoenix200", "Phoenix 200", "Color negative"],
];

export const stockMetadata = {
  "vision250d": {
    "kind": "negative",
    "profile": "vision250d.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "super35",
      "digitalReference": "graded-print"
    }
  },
  "vision500t": {
    "kind": "negative",
    "profile": "vision500t.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "super35",
      "digitalReference": "graded-print"
    }
  },
  "portra400": {
    "kind": "negative",
    "profile": "portra400.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "gold200": {
    "kind": "negative",
    "profile": "gold200.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "cinestill800t": {
    "kind": "negative",
    "profile": "cinestill800t.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "ektachromee100": {
    "kind": "slide",
    "profile": "ektachromee100.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "reference-exposure"
    }
  },
  "trix400": {
    "kind": "monochrome",
    "profile": "trix400.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "provia100f": {
    "kind": "slide",
    "profile": "provia100f.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "reference-exposure"
    }
  },
  "velvia50": {
    "kind": "slide",
    "profile": "velvia50.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "reference-exposure"
    }
  },
  "astia100f": {
    "kind": "slide",
    "profile": "astia100f.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "reference-exposure"
    }
  },
  "pro400h": {
    "kind": "negative",
    "profile": "pro400h.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "eterna500": {
    "kind": "negative",
    "profile": "eterna500.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "super35",
      "digitalReference": "graded-print"
    }
  },
  "ektar100": {
    "kind": "negative",
    "profile": "ektar100.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "superia400": {
    "kind": "negative",
    "profile": "superia400.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "acros100": {
    "kind": "monochrome",
    "profile": "acros100.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "doublex5222": {
    "kind": "monochrome",
    "profile": "doublex5222.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "super35",
      "digitalReference": "graded-print"
    }
  },
  "kodachrome25": {
    "kind": "slide",
    "profile": "kodachrome25.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "reference-exposure"
    }
  },
  "kodachrome64": {
    "kind": "slide",
    "profile": "kodachrome64.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "reference-exposure"
    }
  },
  "cinestill400d": {
    "kind": "negative",
    "profile": "cinestill400d.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "ultramax400": {
    "kind": "negative",
    "profile": "ultramax400.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "pro160ns": {
    "kind": "negative",
    "profile": "pro160ns.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "reala500d": {
    "kind": "negative",
    "profile": "reala500d.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "super35",
      "digitalReference": "graded-print"
    }
  },
  "eternavivid500": {
    "kind": "negative",
    "profile": "eternavivid500.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "super35",
      "digitalReference": "graded-print"
    }
  },
  "hp5plus400": {
    "kind": "monochrome",
    "profile": "hp5plus400.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "tmax100": {
    "kind": "monochrome",
    "profile": "tmax100.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "delta3200": {
    "kind": "monochrome",
    "profile": "delta3200.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  },
  "instaxmini": {
    "kind": "instant",
    "profile": "instaxmini.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "120",
      "digitalReference": "graded-print"
    }
  },
  "phoenix200": {
    "kind": "negative",
    "profile": "phoenix200.json",
    "provenance": "Fotufilm bundled stock profile",
    "resourceRevision": "9242d189b6f8321a27c6f6a345aeb4e5991da569",
    "defaults": {
      "format": "35mm",
      "digitalReference": "graded-print"
    }
  }
};

export const looks = [
  { id: 'clean', name: 'Clean cinema', note: 'Quiet color, fine texture', film: 'vision250d', params: {} },
  { id: 'warm', name: 'Warm portrait', note: 'Soft light, warm skin', film: 'portra400', params: {temperature: 7000, grain: .65}, profile: {screenGrade: 1.7} },
  { id: 'night', name: 'Night lights', note: 'Tungsten, luminous highlights', film: 'vision500t', params: {temperature: 5900, saturation: .95}, profile: {halation: .6} },
  { id: 'eight', name: 'Super 8 diary', note: 'Warm color, visible grain', film: 'gold200', format: 'super8', params: {temperature: 7100, saturation: .9, grain: .85}, profile: {screenGrade: 1.65, halation: -.5} },
  { id: 'slide', name: 'Daylight slide', note: 'Ektachrome, open highlights', film: 'ektachromee100', reference: 'reference-exposure', params: {} },
  { id: 'silver', name: 'Silver screen', note: 'Silver grain, bold contrast', film: 'trix400', format: '16mm', params: {grain: .8}, profile: {screenGrade: 2.5} },
  { id: 'golden', name: 'Golden hour', note: 'Sunlit warmth, soft contrast', film: 'gold200', params: {temperature: 7400, gradeHighlightsWarmth: .2, grain: .65}, profile: {screenGrade: 1.8} },
  { id: 'print', name: 'Cinema print', note: '250D negative, 2383 print', film: 'vision250d', medium: 'vision-2383', params: {saturation: 1.05, grain: .6} },
  { id: 'pastel', name: 'Pastel portrait', note: 'Gentle contrast, soft color', film:'portra400',params:{grain:.35},grading:{finish:{contrast:.87,saturation:.9}} },
  { id: 'neon', name: 'Neon nights', note: 'Cool shadows, luminous color', film:'cinestill800t',profile:{halation:.7},grading:{finish:{lift:[-.008,0,.014],saturation:1.12}} },
  { id: 'editorial', name: 'Cool editorial', note: 'Clean detail, restrained color',film:'vision250d',params:{grain:.35},grading:{finish:{temperature:-.08,contrast:1.08,saturation:.85}} },
  { id: 'noir',name:'Midnight noir',note:'Deep blacks, silver texture',film:'trix400',profile:{screenGrade:2.5},grading:{finish:{contrast:1.12,shadows:-.15}} },
  { id: 'chrome-road', name: 'Chrome road', note: 'Muted color, crisp shadows', film: 'vision250d', params: {grain:.4}, grading:{finish:{contrast:1.12,saturation:.72,temperature:-.03,shadows:-.05}} },
  { id: 'silver-print', name: 'Silver print', note: 'Bleach-inspired, dense contrast', film: 'vision500t', medium:'vision-2383', params:{grain:.65}, grading:{finish:{contrast:1.18,saturation:.48,shadows:-.1}} },
  { id: 'tungsten-print', name: 'Tungsten print', note: 'Evening color, release print', film:'vision500t', medium:'vision-2393', params:{grain:.5}, grading:{finish:{temperature:.04,saturation:.92}} },
  { id: 'soft-window', name: 'Window light', note: 'Soft contrast, fine texture', film:'portra400', format:'120', params:{grain:.25}, profile:{screenGrade:1.8}, grading:{finish:{exposure:.15,contrast:.92,saturation:.94}} },
  { id: 'rose-portrait', name: 'Rose portrait', note: 'Warm mids, a hint of rose', film:'portra400', params:{grain:.4}, grading:{finish:{temperature:.06,tint:.025,contrast:.96,saturation:.92}} },
  { id: 'vivid-daylight', name: 'Vivid daylight', note: 'Rich color, crisp slide contrast', film:'ektachromee100', reference:'reference-exposure', params:{grain:.35}, grading:{finish:{contrast:1.08,saturation:1.16,vibrance:.12}} },
  { id: 'cool-slide', name: 'Blue hour slide', note: 'Cool color, open highlights', film:'ektachromee100', reference:'reference-exposure', params:{grain:.35}, grading:{finish:{temperature:-.08,contrast:.96,saturation:.92}} },
  { id: 'amber-slide', name: 'Amber slide', note: 'Warm color, gentle contrast', film:'ektachromee100', reference:'reference-exposure', params:{grain:.45}, grading:{finish:{temperature:.09,contrast:.94,saturation:1.04}} },
  { id: 'faded-travel', name: 'Faded travel', note: 'Lifted blacks, faded warmth', film:'gold200', format:'35mm', params:{grain:.75}, profile:{screenGrade:1.6}, grading:{finish:{contrast:.9,saturation:.8,lift:[.012,.01,.008],temperature:.04}} },
  { id: 'everyday-35', name: 'Everyday 35', note: 'Punchy color, familiar grain', film:'gold200', format:'35mm', params:{grain:.7}, grading:{finish:{contrast:1.04,saturation:1.08,vibrance:.08}} },
  { id: 'documentary-16', name: 'Documentary 16', note: 'Restrained color, tactile grain', film:'vision250d', format:'16mm', params:{grain:.85}, grading:{finish:{contrast:1.04,saturation:.82,temperature:-.025}} },
  { id: 'soft-silver', name: 'Soft silver', note: 'Gentle monochrome, fine grain', film:'trix400', format:'120', params:{grain:.3}, profile:{screenGrade:1.65}, grading:{finish:{contrast:.92,shadows:.08}} },
  { id:'balanced-slide',name:'Balanced slide',note:'Natural color, open highlights',film:'provia100f',reference:'reference-exposure',params:{grain:.35} },
  { id:'lush-landscape',name:'Lush landscape',note:'Rich greens, deep blues',film:'velvia50',reference:'reference-exposure',params:{grain:.3},grading:{finish:{saturation:1.04}} },
  { id:'soft-slide',name:'Soft slide',note:'Gentle color, smooth contrast',film:'astia100f',reference:'reference-exposure',params:{grain:.3},grading:{finish:{contrast:.96}} },
  { id:'garden-portrait',name:'Garden portrait',note:'Soft greens, delicate color',film:'pro400h',format:'120',params:{grain:.3},grading:{finish:{contrast:.94,saturation:.94}} },
  { id:'quiet-cinema',name:'Quiet cinema',note:'Soft contrast, restrained color',film:'eterna500',params:{grain:.4},grading:{finish:{contrast:.96,saturation:.94}} },
  { id:'vivid-negative',name:'Vivid negative',note:'Bold color, fine texture',film:'ektar100',format:'35mm',params:{grain:.3} },
  { id:'weekend-400',name:'Weekend 400',note:'Everyday color, visible grain',film:'superia400',format:'35mm',params:{grain:.7} },
  { id:'small-town',name:'Small-town 16',note:'Soft color, close-up texture',film:'eterna500',format:'16mm',params:{grain:.8},grading:{finish:{saturation:.85}} },
  { id:'fine-mono',name:'Fine monochrome',note:'Clean detail, quiet grain',film:'acros100',format:'120',params:{grain:.25} },
  { id:'classic-cinema',name:'Classic cinema',note:'Deep monochrome, cinema grain',film:'doublex5222',params:{grain:.65},grading:{finish:{contrast:1.05}} },
  { id:'summer-eight',name:'Summer 8',note:'Sunlit color, small-film texture',film:'gold200',format:'super8',params:{temperature:7200,grain:.8},profile:{screenGrade:1.7},grading:{finish:{contrast:.94,saturation:.95}} },
  { id:'overcast-day',name:'Overcast day',note:'Soft light, subtle cool color',film:'pro400h',params:{grain:.4},grading:{finish:{contrast:.91,temperature:-.025,saturation:.92}} },
  {"id":"reala-dailies","name":"Reala dailies","note":"Daylight cinema, quiet texture","film":"reala500d","params":{"grain":0.35},"grading":{"finish":{"contrast":0.96,"saturation":0.97}}},
  {"id":"dense-release","name":"Dense release print","note":"Vivid negative, deep print contrast","film":"eternavivid500","medium":"vision-2393","params":{"grain":0.5},"profile":{"screenGrade":2.25},"grading":{"finish":{"contrast":1.06,"shadows":-0.04,"saturation":0.95}}},
  {"id":"muted-thriller","name":"Muted thriller","note":"Cold shadows, restrained color","film":"eternavivid500","medium":"vision-2383","params":{"grain":0.6},"grading":{"finish":{"saturation":0.65,"contrast":1.09,"lift":[-0.004,0.003,0.009],"gain":[1.015,1,0.985]}}},
  {"id":"daylight-160","name":"Daylight portrait","note":"Soft color, medium-format texture","film":"pro160ns","format":"120","params":{"grain":0.28},"profile":{"screenGrade":1.8},"grading":{"finish":{"contrast":0.96,"saturation":0.96}}},
  {"id":"warm-interior","name":"Warm interior","note":"Amber light, gentle shadows","film":"cinestill400d","params":{"grain":0.42},"profile":{"screenGrade":1.85},"grading":{"finish":{"temperature":0.065,"shadows":0.05,"contrast":0.96}}},
  {"id":"clean-beauty","name":"Clean beauty","note":"Fine texture, neutral skin tones","film":"pro160ns","format":"120","params":{"grain":0.18},"grading":{"finish":{"contrast":1.025,"saturation":0.92,"highlights":-0.06}}},
  {"id":"travel-chrome","name":"Travel chrome","note":"Kodachrome color, crisp daylight","film":"kodachrome64","format":"35mm","reference":"reference-exposure","params":{"grain":0.5}},
  {"id":"quiet-landscape","name":"Quiet landscape","note":"Fine slide texture, restrained color","film":"kodachrome25","format":"35mm","reference":"reference-exposure","params":{"grain":0.25},"grading":{"finish":{"contrast":0.95,"saturation":0.87}}},
  {"id":"summer-chrome","name":"Summer chrome","note":"Warm slides, vivid color","film":"kodachrome25","format":"35mm","reference":"reference-exposure","params":{"grain":0.45},"grading":{"finish":{"temperature":0.04,"vibrance":0.08,"saturation":1.08}}},
  {"id":"faded-home","name":"Faded home movie","note":"Lifted shadows, small-film texture","film":"ultramax400","format":"super8","params":{"grain":0.9},"profile":{"screenGrade":1.55},"grading":{"finish":{"saturation":0.8,"lift":[0.012,0.009,0.006],"contrast":0.93}}},
  {"id":"seventies-print","name":"Seventies print","note":"Warm print, subdued blues","film":"reala500d","medium":"vision-2383","params":{"grain":0.65},"grading":{"finish":{"temperature":0.07,"saturation":0.86,"gain":[1.02,1,0.97]}}},
  {"id":"cool-telecine","name":"Cool telecine","note":"Cool mids, soft video-era contrast","film":"ultramax400","format":"16mm","params":{"grain":0.6},"profile":{"screenGrade":1.75},"grading":{"finish":{"temperature":-0.065,"contrast":0.94,"lift":[0.004,0.007,0.012],"saturation":0.9}}},
  {"id":"studio-mono","name":"Studio monochrome","note":"Fine grain, sculpted contrast","film":"tmax100","format":"120","params":{"grain":0.25},"profile":{"screenGrade":2.1},"grading":{"finish":{"contrast":1.04}}},
  {"id":"grainy-night","name":"Grainy night","note":"Silver texture, deep night shadows","film":"delta3200","format":"35mm","params":{"grain":0.95},"profile":{"screenGrade":2.25},"grading":{"finish":{"contrast":1.06,"shadows":-0.06}}},
  {"id":"soft-documentary","name":"Soft documentary","note":"Gentle monochrome, visible texture","film":"hp5plus400","format":"16mm","params":{"grain":0.65},"profile":{"screenGrade":1.65},"grading":{"finish":{"contrast":0.94,"shadows":0.04}}},
  {"id":"instant-memory","name":"Instant memory","note":"Instant-film color, gentle warmth","film":"instaxmini","format":"120","params":{"grain":0.55},"profile":{"screenGrade":1.8},"grading":{"finish":{"temperature":0.035,"saturation":0.9,"contrast":0.96}}},
  {"id":"silver-retention","name":"Silver retention","note":"Bleach-inspired, muted dense color","film":"eternavivid500","medium":"vision-2393","params":{"grain":0.75},"profile":{"screenGrade":2.25},"grading":{"finish":{"saturation":0.32,"contrast":1.16,"shadows":-0.06}}},
  {"id":"phoenix-shift","name":"Phoenix shift","note":"Cross-process-inspired color shifts","film":"phoenix200","format":"35mm","params":{"grain":0.65},"profile":{"screenGrade":2.1},"grading":{"finish":{"lift":[-0.004,0.012,0.008],"gain":[1.04,1.015,0.96],"contrast":1.05,"saturation":1.06}}},
];

export const lookGroups = [
  ['all','All', looks.map(look=>look.id)],
  ['cinema','Cinema',['clean','night','print','neon','editorial','chrome-road','silver-print','tungsten-print','quiet-cinema','reala-dailies','dense-release','muted-thriller']],
  ['portrait','Portrait',['warm','pastel','soft-window','rose-portrait','garden-portrait','overcast-day','daylight-160','warm-interior','clean-beauty']],
  ['slide','Slide',['slide','vivid-daylight','cool-slide','amber-slide','balanced-slide','lush-landscape','soft-slide','travel-chrome','quiet-landscape','summer-chrome']],
  ['vintage','Vintage',['eight','golden','faded-travel','everyday-35','documentary-16','weekend-400','small-town','summer-eight','vivid-negative','faded-home','seventies-print','cool-telecine']],
  ['mono','B&W',['silver','noir','soft-silver','fine-mono','classic-cinema','studio-mono','grainy-night','soft-documentary']],
  ['experimental','Experimental',['instant-memory', 'silver-retention', 'phoenix-shift']],
];

export const lookProvenance = 'Original ComfyUI-Fotufilm recipe; Fotufilm stock profiles';
