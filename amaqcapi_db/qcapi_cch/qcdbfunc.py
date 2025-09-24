import os
from loguru import logger

class qcxQCDB:
    def __init__(self, path, dburo, dbthy):
        self.path = path
        self.uroname = dburo
        self.thyname = dbthy
    def set_qcdb_path(self, path):
        self.path = path
    def get_qcdb_path(self):
        return self.path
    def set_qcdb_name(self, slide_type, dbname):
        if slide_type.lower() == 'urine':
            self.uroname = dbname
        elif slide_type.lower() == 'thyroid':
            self.thyname = dbname        
    def get_qcdb_name(self, slide_type):
        if slide_type.lower() == 'urine':
            dbname = self.uroname
        elif slide_type.lower() == 'thyroid':
            dbname = self.thyname
        thisdb = os.path.join(self.path, dbname)
        return thisdb

## -------------------------------------------------------------- 
##  utilities: sqlite3 database operations for QC workflow
## -------------------------------------------------------------- 

def createNewQCxDB(whichmodel, whichdb):
    #if os.path.basename(whichdb) == 'demo_qcxuro.db':
    if whichmodel.lower() == 'aixuro':
        sql_str = "CREATE TABLE IF NOT EXISTS QCxURO ( \
            slidelabel TEXT, zlayer INTEGER, zfocus INTEGER, similarity REAL, \
            suspicious INTEGER, atypical INTEGER, degenerated INTEGER, benign INTEGER, \
            s_avg_ncratio REAL, s_avg_nuclarea REAL, a_avg_ncratio REAL, a_avg_nuclarea REAL, \
            t_avg_ncratio REAL, t_avg_nuclarea REAL, \
            modelProduct TEXT, modelVersion TEXT, \
            medfname TEXT, medfpath TEXT)"
    #elif os.path.basename(whichdb) == 'demo_qcxthy.db':
    elif whichmodel.lower() == 'aixthy':
        sql_str = "CREATE TABLE IF NOT EXISTS QCxTHY ( \
            slidelabel TEXT, zlayer INTEGER, zfocus INTEGER, similarity REAL, \
            category1 INTEGER, category2 INTEGER, category3 INTEGER, category4 INTEGER, \
            category5 INTEGER, category6 INTEGER, \
            trait1 INTEGER, trait2 INTEGER, trait3 INTEGER, trait4 INTEGER, trait5 INTEGER, \
            trait6 INTEGER, trait7 INTEGER, trait8 INTEGER, trait9 INTEGER, trait10 INTEGER, \
            trait11 INTEGER, trait12 INTEGER, trait13 INTEGER, trait14 INTEGER, trait15 INTEGER, \
            trait16 INTEGER, trait17 INTEGER, trait18 INTEGER, trait19 INTEGER, trait20 INTEGER, \
            modelProduct TEXT, modelVersion TEXT, \
            medfname TEXT, medfpath TEXT)"
    try:
        with sqlite3.connect(whichdb) as dbconn:
           cur = dbconn.cursor()
           cur.execute(sql_str)
           dbconn.commit()
           logger.trace(f'{os.path.basename(whichdb)} created!')
    except sqlite3.OperationalError as e:
        logger.error(f'create new database {whichdb} failed, {e}')

def querySlideAnalyzedMetadata(slide_id, slide_type, thisdb):
    if slide_type.lower() == 'urine':
        #dbname = 'demo_qcxuro.db'
        tblname = 'QCxURO'
    elif slide_type.lower() == 'thyroid':
        #dbname = 'demo_qcxthy.db'
        tblname = 'QCxTHY'
    #thisdb = os.path.join(qcxDBpath, dbname)
    metajson = []
    try:
        with sqlite3.connect(thisdb) as dbconn:
            cur = dbconn.cursor()
            cur.execute(f'SELECT * FROM {tblname} WHERE slidelabel = "{slide_id}"')
            rows = cur.fetchall()
            for row in rows:
                thismeta = {}
                if slide_type.lower() == 'urine':
                    thismeta['suspicious'], thismeta['atypical'] = row[4], row[5]
                    thismeta['TOP24_average_NC_ratio'] = row[12]
                    thismeta['TOP24_average_Nucleus_Area'] = row[13]
                    thismeta['model'] = f'{row[14]} {row[15]}'
                    thismeta['filepath'] = os.path.join(row[17], row[16])
                elif slide_type.lower() == 'thyroid':
                    thismeta['follicular'] = row[4]
                    if '2024.2' in row[31]:     # model version
                        thismeta['hurthle'] = row[5]
                        thismeta['histiocytes'] = row[6]
                        thismeta['lymphocytes'] = row[7]
                        thismeta['colloid'] = row[8]
                    elif '2025.2' in row[31]:
                        thismeta['oncocytic'] = row[5]
                        thismeta['lymphocytes'] = row[7]
                        thismeta['histiocytes'] = row[8]
                        thismeta['colloid'] = row[9]
                    thismeta['model'] = f'{row[30]} {row[31]}'
                    thismeta['filepath'] = os.path.join(row[33], row[32])
                metajson.append(thismeta)
    except sqlite3.OperationalError as e:
        logger.error(f'something wrong when querying slide {slide_id}, {e}')
    if len(metajson) > 1:
        logger.warning(f'more than one slide {slide_id} found in database, please check!')
    return metajson

def saveInferenceMetadata2DB(medata, counts, tclist, dbname):
    if counts == [] or len(tclist) == 0:
        logger.warning('no inference metadata to save')
        return
    if os.path.isfile(dbname) == False:
        logger.warning(f'database {dbname} does not exist')
        createNewQCxDB(medata['modeln'], dbname)
    labelname = medata['label']
    modelname, model_ver = medata['modeln'], medata['modelv']
    medfile, medpath = medata['medfile'], medata['medpath']
    ## check if this slide already existed
    if modelname.lower() == 'aixuro':
        slidetype = 'urine'
    elif modelname.lower() == 'aixthy':
        slidetype = 'thyroid'
    mdata = querySlideAnalyzedMetadata(labelname, slidetype)
    if mdata != None:
        for k in range(len(mdata)):
            if mdata[k]['model'] == f'{modelname} {model_ver}':
                logger.error(f'slide {labelname} already existed in database {dbname}')
                return
        logger.warning(f"slide {labelname} already existed in database {dbname}, but analyzed by {modelname} {model_ver} this time")
    ##
    if medata['modeln'].lower() == 'aixuro':
        s_avg_ncratio, s_avg_nuclarea, a_avg_ncratio, a_avg_nuclarea = getUROaverageOfSAcells(tclist)
        _, t_avg_ncratio, t_avg_nuclarea = getUROaverageOfTopCells(tclist)
        sql_head = "INSERT INTO QCxURO \
            (slidelabel, zlayer, zfocus, similarity, suspicious, atypical, degenerated, benign, \
            s_avg_ncratio, s_avg_nuclarea, a_avg_ncratio, a_avg_nuclarea, \
            t_avg_ncratio, t_avg_nuclarea, modelProduct, modelVersion, \
            medfname, medfpath) VALUES "
        sql_tail = f"('{labelname}', {medata['zlayer']}, {medata['zfocus']}, {medata['similarity']}, \
            {counts[2]}, {counts[3]}, {counts[7]}, {counts[4]}, \
            {s_avg_ncratio}, {s_avg_nuclarea}, {a_avg_ncratio}, {a_avg_nuclarea}, \
            {t_avg_ncratio}, {t_avg_nuclarea}, \
            '{modelname}', '{model_ver}', '{medfile}', '{medpath}')"
    elif medata['modeln'].lower() == 'aixthy':
        thistrait = countNumberOfTHYtraits(tclist, 20)
        sql_head = "INSERT INTO QCxTHY \
            (slidelabel, zlayer, zfocus, similarity, \
            category1, category2, category3, category4, category5, category6, \
            trait1, trait2, trait3, trait4, trait5, trait6, trait7, trait8, trait9, trait10, \
            trait11, trait12, trait13, trait14, trait15, trait16, trait17, trait18, trait19, trait20, \
            modelProduct, modelVersion, medfname, medfpath) VALUES "
        sql_tail = f"('{labelname}', {medata['zlayer']}, {medata['zfocus']}, {medata['similarity']}, \
            {counts[1]}, {counts[2]}, {counts[3]}, {counts[4]}, {counts[5]}, {counts[6]}, \
            {thistrait[0]}, {thistrait[1]}, {thistrait[2]}, {thistrait[3]}, {thistrait[4]}, \
            {thistrait[5]}, {thistrait[6]}, {thistrait[7]}, {thistrait[8]}, {thistrait[9]}, \
            {thistrait[10]}, {thistrait[11]}, {thistrait[12]}, {thistrait[13]}, {thistrait[14]}, \
            {thistrait[15]}, {thistrait[16]}, {thistrait[17]}, {thistrait[18]}, {thistrait[19]}, \
            '{modelname}', '{model_ver}', '{medfile}', '{medpath}')"
    sql_str = sql_head + sql_tail
    try:
        with sqlite3.connect(dbname) as dbconn:
            cur = dbconn.cursor()
            cur.execute(sql_str)
            dbconn.commit()
        logger.info(f'{os.path.basename(dbname)} updated!')
    except sqlite3.OperationalError as e:
        logger.error(f'save inference metadata to database {dbname} failed, {e}')

