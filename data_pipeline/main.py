from data_pipeline.cvm.fetcher import fetcher
from data_pipeline.cvm.reader import reader
from data_pipeline.normalization.normalize_df import normalized_coll
from data_pipeline.search.matcher import matcher

cvmBytes = fetcher()
cvm_df = reader(cvmBytes)

cvm_df = normalized_coll(cvm_df)

result = matcher('inter', cvm_df)
print(result)

