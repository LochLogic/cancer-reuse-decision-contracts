library(admiral)
library(dplyr)
library(rlang)
# Entirely invented histories. Day zero is a synthetic diagnosis date.
adsl <- tibble(STUDYID='SYNTHETIC', USUBJID=paste0('H',1:7),
 DIAGDT=as.Date('2020-01-01'), RANDDT=as.Date('2020-01-01')+c(0,30,0,0,0,0,0),
 PROGDT=as.Date('2020-01-01')+c(100,100,NA,120,NA,NA,NA),
 DTHDT=as.Date('2020-01-01')+c(NA,NA,100,NA,NA,NA,150),
 DEATH_WITH_TUMOR=c(FALSE,FALSE,FALSE,FALSE,FALSE,FALSE,TRUE),
 LASTDT=as.Date('2020-01-01')+c(180,180,90,180,180,NA,120),
 PRETHERAPYDT=as.Date('2020-01-01')+c(NA,NA,NA,60,NA,NA,NA),
 NEWDRGDT=as.Date('2020-01-01')+c(NA,NA,NA,80,NA,NA,NA))
pd <- event_source(dataset_name='adsl',date=PROGDT)
death <- event_source(dataset_name='adsl',date=DTHDT)
tumor_death <- event_source(dataset_name='adsl',date=DTHDT,filter=DEATH_WITH_TUMOR == TRUE)
last <- censor_source(dataset_name='adsl',date=LASTDT)
non_tumor_death <- censor_source(dataset_name='adsl',date=DTHDT,filter=!DEATH_WITH_TUMOR)
pre <- censor_source(dataset_name='adsl',date=PRETHERAPYDT)
# Version 1.4.2 implements observation cutoffs through source filters.
pd_cut <- event_source(dataset_name='adsl',date=PROGDT,filter=is.na(NEWDRGDT) | PROGDT <= NEWDRGDT)
death_cut <- event_source(dataset_name='adsl',date=DTHDT,filter=is.na(NEWDRGDT) | DTHDT <= NEWDRGDT)
last_cut <- censor_source(dataset_name='adsl',date=LASTDT,filter=is.na(NEWDRGDT) | LASTDT <= NEWDRGDT)
derive <- function(label,origin,ev,cs=list(last)) {
  x <- derive_param_tte(dataset_adsl=adsl,source_datasets=list(adsl=adsl),
     start_date=!!origin,event_conditions=ev,censor_conditions=cs,
     set_values_to=exprs(PARAMCD=!!label),check_type='error')
  # Comparator uses elapsed days, not the conventional inclusive ADaM AVAL.
  x %>% transmute(history=USUBJID,profile=PARAMCD,
                 elapsed_days=as.numeric(ADT-STARTDT),censored=CNSR)
}
z <- bind_rows(derive('DIAG_ANY_DEATH',sym('DIAGDT'),list(pd,death)),
 derive('RAND_ANY_DEATH',sym('RANDDT'),list(pd,death)),
 derive('DIAG_DEATH_WITH_TUMOR',sym('DIAGDT'),list(pd,tumor_death),list(last,non_tumor_death)),
 derive('RAND_THERAPY_CUTOFF',sym('RANDDT'),list(pd_cut,death_cut),list(last_cut,pre)))
jsonlite::toJSON(list(runtime=list(R=as.character(getRversion()),admiral=as.character(packageVersion('admiral'))),
 scope='Synthetic illustrations of specification mechanisms, not full TCGA-CDR or regulatory endpoint implementations.',
 outputs=z),auto_unbox=TRUE,pretty=TRUE,na='null')
