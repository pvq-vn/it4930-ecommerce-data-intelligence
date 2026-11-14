| Architecture                         | Model Type                     |   Accuracy |   Macro F1 |   Weighted F1 |   F1 (Neg) |   F1 (Neu) |   F1 (Pos) |
|:-------------------------------------|:-------------------------------|-----------:|-----------:|--------------:|-----------:|-----------:|-----------:|
| TF-IDF + LogisticRegression_balanced | Classical ML                   |     0.8981 |     0.5901 |        0.9116 |     0.5623 |     0.2526 |     0.9556 |
| TF-IDF + LinearSVC_balanced          | Classical ML                   |     0.9257 |     0.5778 |        0.9227 |     0.5606 |     0.2032 |     0.9697 |
| TF-IDF + ComplementNB                | Classical ML                   |     0.8638 |     0.5226 |        0.8856 |     0.4453 |     0.1867 |     0.9359 |
| TF-IDF + MultinomialNB_unweighted    | Classical ML                   |     0.918  |     0.3415 |        0.8804 |     0.0671 |     0      |     0.9573 |
| PhoBERT (vinai/phobert-base-v2)      | Pre-trained Transformer (SOTA) |     0.9223 |     0.6491 |        0.9302 |     0.6316 |     0.3472 |     0.9686 |