"""Build the US Montessori private schools dataset from the NCES Private School Universe Survey (PSS).

Inputs  : the public-use files of the 18 PSS waves (1989-90 to 2023-24), downloaded from https://nces.ed.gov/surveys/pss/pssdata.asp
          and unzipped into PSS_RAW (default ./raw), with the NCES SAS label/format programs of each wave in PSS_RAW/fmt/<wave>/
Outputs : data/montessori_private_schools_1989_2024.csv and data/private_school_universe_totals.csv

A school counts as Montessori when at least one of these is true in a given wave:
  - montessori_program_type : the school chose "Montessori" as its type of school (official PSS item)
  - ams_member / ami_member / other_montessori_member : the school reports membership in a Montessori association
  - name_has_montessori : the school name contains "Montessori" (names are public from 2005-06 only)
"""
import glob, json, os, re
import numpy as np
import pandas as pd

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RAW = os.environ.get('PSS_RAW', os.path.join(ROOT, 'raw'))
FMT = f'{RAW}/fmt'
OUT = os.path.join(ROOT, 'data')
os.makedirs(OUT, exist_ok=True)

STATE_FIPS = {'AL':'01','AK':'02','AZ':'04','AR':'05','CA':'06','CO':'08','CT':'09','DE':'10','DC':'11','FL':'12','GA':'13','HI':'15','ID':'16','IL':'17','IN':'18','IA':'19','KS':'20','KY':'21','LA':'22','ME':'23','MD':'24','MA':'25','MI':'26','MN':'27','MS':'28','MO':'29','MT':'30','NE':'31','NV':'32','NH':'33','NJ':'34','NM':'35','NY':'36','NC':'37','ND':'38','OH':'39','OK':'40','OR':'41','PA':'42','RI':'44','SC':'45','SD':'46','TN':'47','TX':'48','UT':'49','VT':'50','VA':'51','WA':'53','WV':'54','WI':'55','WY':'56'}
STATE_NAME = {'AL':'Alabama','AK':'Alaska','AZ':'Arizona','AR':'Arkansas','CA':'California','CO':'Colorado','CT':'Connecticut','DE':'Delaware','DC':'District of Columbia','FL':'Florida','GA':'Georgia','HI':'Hawaii','ID':'Idaho','IL':'Illinois','IN':'Indiana','IA':'Iowa','KS':'Kansas','KY':'Kentucky','LA':'Louisiana','ME':'Maine','MD':'Maryland','MA':'Massachusetts','MI':'Michigan','MN':'Minnesota','MS':'Mississippi','MO':'Missouri','MT':'Montana','NE':'Nebraska','NV':'Nevada','NH':'New Hampshire','NJ':'New Jersey','NM':'New Mexico','NY':'New York','NC':'North Carolina','ND':'North Dakota','OH':'Ohio','OK':'Oklahoma','OR':'Oregon','PA':'Pennsylvania','RI':'Rhode Island','SC':'South Carolina','SD':'South Dakota','TN':'Tennessee','TX':'Texas','UT':'Utah','VT':'Vermont','VA':'Virginia','WA':'Washington','WV':'West Virginia','WI':'Wisconsin','WY':'Wyoming'}
FIPS_STATE = {v: k for k, v in STATE_FIPS.items()}

# variable map per wave (checked against the NCES label and format programs, see scripts/labels.py)
W = {
 '8990': dict(file='PSS8990_SAS7BDAT/pss8990_pu.sas7bdat', id='EPIN', city='CITY', state='STATE', zip='EZIP', type='PSS112', ams='PSS072', other='PSS073'),
 '9192': dict(file='PSS9192_SAS7BDAT/pss9192_pu.sas7bdat', id='EPIN', city='ECITY', state='ESTABB', zip='EZIP', type='PSC105', ams='PSC071', other='PSC072'),
 '9394': dict(file='PSS9394_SAS7BDAT/pss9394_pu.sas7bdat', id='PPIN', city='PCITY', state='PSTABB', zip='PZIP', cnty='PCNTY', type='P280', ams='P420', other='P425', wt='PFNLWT'),
 '9596': dict(file='PSS9596_SAS7BDAT/pss9596_pu.sas7bdat', id='QPIN', city='QCITY', state='QSTABB', zip='QZIP', cnty='QCNTY', type='P415', ams='P470', other='P475', wt='QFNLWT', prek='P145', k='P165', prek_enr='P150', k_enr='P170'),
 '9798': dict(file='PSS9798_SAS7BDAT/pss9798_pu.sas7bdat', id='RPIN', city='RCITY', state='RSTABB', zip='RZIP', cnty='RCNTY', type='P415', ams='P540', other='P545', wt='RFNLWT'),
 '9900': dict(file='PSS9900_SAS7BDAT/PSS9900_PU.sas7bdat', id='SPIN', city='SCITY', state='SSTABB', zip='SZIP', cnty='SCNTY', type='P415', ams='P540', other='P545', wt='SFNLWT'),
 '0102': dict(file='PSS0102_SAS7BDAT/pss0102_pu.sas7bdat', type='P415', ams='P540', other='P545'),
 '0304': dict(file='PSS0304_SAS7BDAT/pss0304_pu.sas7bdat', type='P415', ams='P540', other='P545'),
 '0506': dict(file='PSS0506_SAS7BDAT/pss0506_pu.sas7bdat', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '0708': dict(file='PSS0708_SAS7BDAT/PSS0708_PU.sas7bdat', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '0910': dict(file='PSS0910_SAS7BDAT/pss0910_pu.sas7bdat', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '1112': dict(file='pss1112_pu_sas7bdat/New folder/pss1112_pu.sas7bdat', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '1314': dict(file='pss1314_pu_csv/pss1314_pu.csv', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '1516': dict(file='pss1516_pu_csv/pss1516_pu.csv', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '1718': dict(file='pss1718_pu_csv/pss1718_pu.csv', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '1920': dict(file='pss1920_pu_csv/pss1920_pu.csv', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '2122': dict(file='pss2122_pu_csv/pss2122_pu.csv', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
 '2324': dict(file='pss2324_pu_csv/pss2324_pu.csv', type='P415', ams='P540', ami='P542', other='P545', name='PINST'),
}
DEFAULTS = dict(id='PPIN', city='PCITY', state='PSTABB', zip='PZIP', cnty='PCNTY', wt='PFNLWT', prek='P145', k='P155', prek_enr='P150', k_enr='P160')

TYPE_LABEL = {1: 'Regular elementary or secondary', 2: 'Montessori', 3: 'Special program emphasis', 4: 'Special education',
              5: 'Career/technical/vocational', 6: 'Alternative/other', 7: 'Early childhood program/child care center'}
TYPOLOGY_LABEL = {1: 'Catholic, parochial', 2: 'Catholic, diocesan', 3: 'Catholic, private', 4: 'Other religious, conservative Christian',
                  5: 'Other religious, affiliated', 6: 'Other religious, unaffiliated', 7: 'Nonsectarian, regular',
                  8: 'Nonsectarian, special emphasis', 9: 'Nonsectarian, special education'}
LEVEL_LABEL = {1: 'Elementary', 2: 'Secondary', 3: 'Combined elementary and secondary'}
OLD_LOCALE_GROUP = {1: 'City', 2: 'City', 3: 'Suburb', 4: 'Suburb', 5: 'Town', 6: 'Town', 7: 'Rural', 8: 'Rural'}
ULOCALE_LABEL = {11: 'City, large', 12: 'City, midsize', 13: 'City, small', 21: 'Suburb, large', 22: 'Suburb, midsize', 23: 'Suburb, small',
                 31: 'Town, fringe', 32: 'Town, distant', 33: 'Town, remote', 41: 'Rural, fringe', 42: 'Rural, distant', 43: 'Rural, remote'}

def survey_year(w):
    a = int(w[:2]); a = a + (1900 if a > 50 else 2000)
    return f'{a}-{str(a + 1)[2:]}', a + 1

def sas_formats(wave):
    """value label blocks from the wave's SAS program -> {format_name_upper: {code: label}}"""
    txt = '\n'.join(open(f, encoding='latin-1').read() for f in glob.glob(f'{FMT}/{wave}/*.sas'))
    out = {}
    for m in re.finditer(r'(?is)\bvalue\s+(\$?\w+)\s+(.*?);', txt):
        name, body = m.group(1).upper().rstrip('.'), m.group(2)
        pairs = re.findall(r"(-?\d+)\s*=\s*['\"]([^'\"]*)['\"]", body)
        if pairs:
            out[name] = {int(k): v.strip() for k, v in pairs}
    return out

def read(path):
    p = f'{RAW}/{path}'
    if p.endswith('.csv'):
        df = pd.read_csv(p, low_memory=False, encoding='latin-1')
    else:
        df = pd.read_sas(p, encoding='latin-1')
    df.columns = [re.sub(r'[^A-Z0-9_]', '', c.upper()) for c in df.columns]
    return df

def yes(s):
    s = pd.to_numeric(s, errors='coerce')
    if s.dropna().empty:
        return pd.Series(False, index=s.index)
    if s.max() <= 2:                       # 1 = yes, 0 or 2 = no
        return s.eq(1)
    return s.notna() & s.gt(0)             # 1989-92 files: a code is present only when the box was ticked

def first(df, pattern):
    for c in df.columns:
        if re.fullmatch(pattern, c):
            return c
    return None

def clean_text(s):
    return s.astype(str).str.strip().replace({'nan': '', 'None': '', 'NaN': ''}).str.replace(r'\s+', ' ', regex=True)

CANON = {1: 'Ungraded', 2: 'Prekindergarten', 3: 'Kindergarten', 4: 'Transitional kindergarten', 5: 'Transitional first grade',
         6: 'Grade 1', 7: 'Grade 2', 8: 'Grade 3', 9: 'Grade 4', 10: 'Grade 5', 11: 'Grade 6', 12: 'Grade 7', 13: 'Grade 8',
         14: 'Grade 9', 15: 'Grade 10', 16: 'Grade 11', 17: 'Grade 12'}

def norm_grade(t):
    t = (t or '').strip()
    t = re.sub(r'^(Lowest|Highest) grade in school is ', '', t, flags=re.I)
    t = re.sub(r'^\d+\s*=\s*', '', t)
    if not t: return ''
    low = t.lower()
    if 'less than' in low: return 'Ungraded or below grade 1'
    if 'ungraded' in low: return 'Ungraded'
    if 'transitional' in low and ('first' in low or '1st' in low): return 'Transitional first grade'
    if 'transitional' in low: return 'Transitional kindergarten'
    if low.startswith(('prek', 'pre-k', 'nursery', 'pk')) or 'prekindergarten' in low: return 'Prekindergarten'
    if low.startswith(('kindergarten', 'kg', 'k ')) or low in ('k',): return 'Kindergarten'
    m = re.search(r'(\d+)', low)
    if m and 1 <= int(m.group(1)) <= 12: return f'Grade {int(m.group(1))}'
    return t

def grade_label(df, wave, var, fmts):
    if not var:
        return pd.Series('', index=df.index)
    codes = pd.to_numeric(df[var], errors='coerce')
    base = re.sub(r'\d+$', '', re.sub(r'^[A-Z](?=[LH])', '', var))           # QHIGR6 -> HIGR
    keys = [var + 'F', re.sub(r'\d+$', '', var) + 'F', base + 'F', '$' + base + 'F', ('LOGRADEF' if 'LO' in var else 'HIGRADEF')]
    f = next((fmts[k] for k in keys if k in fmts), None)
    if f:                                       # the wave's own code list, read from its format program
        return codes.map(lambda c: norm_grade(f.get(int(c), '')) if pd.notna(c) else '')
    return codes.map(lambda c: CANON.get(int(c), '') if pd.notna(c) else '')   # 1 to 17 code list used from 2005-06 on

frames, totals = [], []
for wave, cfg in W.items():
    cfg = {**DEFAULTS, **cfg}
    df = read(cfg['file'])
    sy, ye = survey_year(wave)
    fmts = sas_formats(wave)
    col = lambda k: cfg.get(k) if cfg.get(k) in df.columns else None
    wt = col('wt')
    weight = pd.to_numeric(df[wt], errors='coerce') if wt else pd.Series(np.nan, index=df.index)
    if wave == '9394':   # the 1993-94 public file weights sum to ~100k schools vs ~26k published by NCES, so they are not released here
        weight = pd.Series(np.nan, index=df.index); wt = None
    ptype = pd.to_numeric(df[cfg['type']], errors='coerce')
    flags = pd.DataFrame({
        'montessori_program_type': ptype.eq(2),
        'ams_member': yes(df[cfg['ams']]) if col('ams') else False,
        'ami_member': yes(df[cfg['ami']]) if cfg.get('ami') and col('ami') else False,
        'other_montessori_member': yes(df[cfg['other']]) if col('other') else False,
    }, index=df.index)
    name = clean_text(df[cfg['name']]) if cfg.get('name') and col('name') else pd.Series('', index=df.index)
    flags['name_has_montessori'] = name.str.contains('montessori', case=False)
    flags['montessori_any'] = flags.any(axis=1)

    state = clean_text(df[col('state')]) if col('state') else pd.Series('', index=df.index)
    if wave == '8990' and state.str.fullmatch(r'\d+').mean() > .5:   # 1989-90 stores the state as a FIPS code
        state = state.str.zfill(2).map(FIPS_STATE).fillna(state)
    cnty = pd.to_numeric(df[col('cnty')], errors='coerce') if col('cnty') else pd.Series(np.nan, index=df.index)
    lat = first(df, r'LATITUDE\d*'); lon = first(df, r'LONGITUDE\d*')
    uloc = first(df, r'ULOCALE\d*'); oloc = 'LOCALE' if 'LOCALE' in df.columns else None
    if uloc:
        loc_code = pd.to_numeric(df[uloc], errors='coerce')
        loc_detail = loc_code.map(ULOCALE_LABEL).fillna('')
        loc_group = loc_detail.str.split(',').str[0]
    elif oloc:
        loc_code = pd.to_numeric(df[oloc], errors='coerce')
        loc_detail = pd.Series('', index=df.index)
        loc_group = loc_code.map(OLD_LOCALE_GROUP).fillna('')
    else:
        loc_code = pd.Series(np.nan, index=df.index); loc_detail = loc_group = pd.Series('', index=df.index)
    logr = first(df, r'[A-Z]?LOGR(ADE|\d+)'); higr = first(df, r'[A-Z]?HIGR(ADE|\d+)')
    num = lambda k: pd.to_numeric(df[col(k)], errors='coerce') if col(k) else pd.Series(np.nan, index=df.index)

    rec = pd.DataFrame({
        'survey_year': sy, 'school_year_end': ye,
        'school_id': clean_text(df[col('id')]) if col('id') else '',
        'school_name': name,
        'city': clean_text(df[col('city')]).str.title() if col('city') else '',
        'state': state, 'state_name': state.map(STATE_NAME).fillna(''),
        'zip5': clean_text(df[col('zip')]).str[:5].str.zfill(5).replace('00000', '') if col('zip') else '',
        'county_fips': [(STATE_FIPS.get(s, '') + str(int(c)).zfill(3)) if pd.notna(c) and STATE_FIPS.get(s) else '' for s, c in zip(state, cnty)],
        'latitude': pd.to_numeric(df[lat], errors='coerce') if lat else np.nan,
        'longitude': pd.to_numeric(df[lon], errors='coerce') if lon else np.nan,
        'locale_group': loc_group, 'locale_detail': loc_detail,
        'program_type': ptype.map(TYPE_LABEL).fillna(''),
        'religious_typology': pd.to_numeric(df['TYPOLOGY'], errors='coerce').map(TYPOLOGY_LABEL).fillna('') if 'TYPOLOGY' in df.columns else '',
        'level': pd.to_numeric(df['LEVEL'], errors='coerce').map(LEVEL_LABEL).fillna('') if 'LEVEL' in df.columns else '',
        'lowest_grade': grade_label(df, wave, logr, fmts), 'highest_grade': grade_label(df, wave, higr, fmts),
        'prek_offered': num('prek').map({1: True, 2: False}), 'kindergarten_offered': num('k').map({1: True, 2: False}),
        'students_k12': pd.to_numeric(df['NUMSTUDS'], errors='coerce') if 'NUMSTUDS' in df.columns else np.nan,
        'students_prek': num('prek_enr'), 'students_kindergarten': num('k_enr'),
        'teachers_fte_k12': pd.to_numeric(df['NUMTEACH'], errors='coerce') if 'NUMTEACH' in df.columns else np.nan,
        'survey_weight': weight,
    })
    rec = pd.concat([rec, flags], axis=1)
    rec['religious_or_nonsectarian'] = np.where(rec['religious_typology'].str.startswith('Nonsectarian'), 'Nonsectarian',
                                                np.where(rec['religious_typology'].eq(''), '', 'Religious'))
    frames.append(rec[rec.montessori_any])
    totals.append(dict(survey_year=sy, school_year_end=ye, private_schools_in_file=len(df),
                       private_schools_weighted=round(weight.sum()) if wt else np.nan))
    print(sy, len(df), 'montessori_any', int(flags.montessori_any.sum()), 'type', int(flags.montessori_program_type.sum()))

schools = pd.concat(frames, ignore_index=True)
schools['latitude'] = schools['latitude'].round(6); schools['longitude'] = schools['longitude'].round(6)
for c in ['students_k12', 'students_prek', 'students_kindergarten']:
    schools[c] = schools[c].round().astype('Int64')
schools['teachers_fte_k12'] = schools['teachers_fte_k12'].round(1)
schools['survey_weight'] = schools['survey_weight'].round(4)
schools.to_csv(f'{OUT}/montessori_private_schools_1989_2024.csv', index=False)
pd.DataFrame(totals).to_csv(f'{OUT}/private_school_universe_totals.csv', index=False)
print('rows', len(schools))
