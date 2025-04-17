from loguru import logger

def encode_with_fallback(df, col, encoder):
    """
    Safely encodes a dataframe column using a provided LabelEncoder.
    Falls back to the first known label if unseen values are found.

    Args:
        df (pd.DataFrame): Input DataFrame with raw feature values.
        col (str): Column name to encode.
        encoder (dict): Dictionary of trained LabelEncoders.

    Returns:
        None — modifies df[col] in place.
    """
    if col not in df.columns:
        logger.warning(f"[ENCODE] Column '{col}' is missing from DataFrame. Skipping encoding.")
        return

    if col not in encoder:
        logger.warning(f"[ENCODE] No encoder found for column '{col}'. Skipping encoding.")
        return

    le = encoder[col]
    fallback_val = le.classes_[0]
    encoded = []

    for val in df[col]:
        try:
            encoded_val = le.transform([val])[0] if val in le.classes_ else le.transform([fallback_val])[0]
            if val not in le.classes_:
                logger.debug(f"[ENCODE] Used fallback for unseen value '{val}' in column '{col}'")
        except Exception as e:
            logger.error(f"[ENCODE] Failed to encode value '{val}' in '{col}': {e}")
            encoded_val = le.transform([fallback_val])[0]
        encoded.append(encoded_val)

    df[col] = encoded
