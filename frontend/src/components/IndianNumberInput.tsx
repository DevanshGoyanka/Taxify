import React from 'react';

interface IndianNumberInputProps {
  value: number;
  onChange: (value: number) => void;
  placeholder?: string;
  style?: React.CSSProperties;
  disabled?: boolean;
}

export function IndianNumberInput({ value, onChange, placeholder = '0', style, disabled = false }: IndianNumberInputProps) {
  const [displayValue, setDisplayValue] = React.useState('');
  const [isFocused, setIsFocused] = React.useState(false);

  // Format number with Indian comma style (lakhs/crores)
  const formatIndianNumber = (num: number) => {
    if (num == null || num === 0) return '0';
    // Round to integer to avoid floating point precision issues
    const rounded = Math.round(num);
    const numStr = rounded.toString();
    
    // Indian formatting: last 3 digits, then groups of 2
    let formatted = '';
    const len = numStr.length;
    
    if (len <= 3) {
      formatted = numStr;
    } else {
      formatted = numStr.slice(-3);
      let remaining = numStr.slice(0, -3);
      
      while (remaining.length > 0) {
        if (remaining.length <= 2) {
          formatted = remaining + ',' + formatted;
          remaining = '';
        } else {
          formatted = remaining.slice(-2) + ',' + formatted;
          remaining = remaining.slice(0, -2);
        }
      }
    }
    
    return formatted;
  };

  // Remove commas for parsing
  const parseIndianNumber = (str: string) => {
    return str.replace(/,/g, '');
  };

  React.useEffect(() => {
    if (!isFocused) {
      setDisplayValue(value == null || value === 0 ? '' : formatIndianNumber(value));
    }
  }, [value, isFocused]);

  const handleFocus = (e: React.FocusEvent<HTMLInputElement>) => {
    setIsFocused(true);
    // Clear the field if it's 0 or empty
    if (value === 0 || value === null) {
      setDisplayValue('');
      e.target.value = '';
    } else {
      // Show raw number without commas for editing
      setDisplayValue(value.toString());
      e.target.value = value.toString();
    }
  };

  const handleBlur = () => {
    setIsFocused(false);
    // Reformat with commas when focus is lost
    setDisplayValue(value === 0 ? '' : formatIndianNumber(value));
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (disabled) return;
    
    const rawValue = parseIndianNumber(e.target.value);
    // Only allow integers, no decimals
    const numValue = rawValue === '' ? 0 : Math.round(Number(rawValue));
    
    if (!isNaN(numValue)) {
      setDisplayValue(e.target.value);
      onChange(numValue);
    }
  };

  return (
    <input
      type="text"
      value={displayValue}
      onChange={handleChange}
      onFocus={handleFocus}
      onBlur={handleBlur}
      placeholder={placeholder}
      disabled={disabled}
      style={{
        fontFamily: 'DM Mono',
        ...style
      }}
    />
  );
}
