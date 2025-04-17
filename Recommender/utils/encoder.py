# Filename: recommender/utils/encoder.py

from loguru import logger

def encode_with_fallback(df, col, encoder):
    """
    Safely encodes a DataFrame column using the provided LabelEncoder.
    Falls back to the first seen class if an unseen value is encountered.

    Args:
        df (pd.DataFrame): Input DataFrame
        col (str): Column name to encode
        encoder (dict): Dictionary of LabelEncoders

    Returns:
        None (modifies df in-place)
    """
    if col not in df.columns:
        logger.warning(f"[ENCODE] Missing column in DataFrame: {col}")
        return

    if col not in encoder:
        logger.warning(f"[ENCODE] Missing encoder for column: {col}")
        return

    le = encoder[col]
    encoded = []

    for val in df[col]:
        try:
            if val in le.classes_:
                encoded_val = le.transform([val])[0]
            else:
                fallback_val = le.classes_[0]
                encoded_val = le.transform([fallback_val])[0]
                logger.debug(f"[ENCODE] Fallback for unseen value '{val}' in column '{col}'")
            encoded.append(encoded_val)
        except Exception as e:
            logger.error(f"[ENCODE] Error encoding value '{val}' in column '{col}': {e}")
            encoded.append(le.transform([le.classes_[0]])[0])  # safest fallback

    df[col] = encoded
