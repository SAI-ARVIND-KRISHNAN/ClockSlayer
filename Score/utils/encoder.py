from loguru import logger

def encode_with_fallback(df, col, encoder):
    """
    Applies LabelEncoder to a column with fallback for unseen values.
    If a value isn't in the encoder's classes_, the first known class is used.
    """
    if col not in df.columns:
        logger.warning(f"[ENCODE] Column '{col}' not found in DataFrame.")
        return

    if col not in encoder:
        logger.warning(f"[ENCODE] No encoder found for column '{col}'.")
        return

    le = encoder[col]
    fallback = le.classes_[0]

    encoded = []
    for val in df[col]:
        if val in le.classes_:
            encoded_val = le.transform([val])[0]
        else:
            logger.debug(f"[ENCODE] Fallback used for '{col}': '{val}' → '{fallback}'")
            encoded_val = le.transform([fallback])[0]
        encoded.append(encoded_val)

    df[col] = encoded
