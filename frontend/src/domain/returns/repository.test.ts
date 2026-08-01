import { beforeEach, describe, expect, it, vi } from 'vitest';
import axiosInstance from '../../api/axiosInstance';
import { createEmptyReturnDraft } from './factory';
import { HttpReturnRepository } from './repository';

vi.mock('../../api/axiosInstance',()=>({default:{get:vi.fn(),put:vi.fn()}}));

describe('HttpReturnRepository',()=>{
  beforeEach(()=>vi.clearAllMocks());
  it('loads and supplies requested assessment year when backend omits it',async()=>{vi.mocked(axiosInstance.get).mockResolvedValue({data:{form:'ITR-1',name:'A'}});const result=await new HttpReturnRepository().get('a/b','2026-27');expect(axiosInstance.get).toHaveBeenCalledWith('/clients/a%2Fb/itr/2026-27');expect(result).toMatchObject({assessmentYear:'2026-27',personal:{name:'A'}});});
  it('ignores status PUT response and returns an independent normalized submitted draft',async()=>{vi.mocked(axiosInstance.put).mockResolvedValue({data:{message:'saved',itr_type:'ITR-4'}});const draft=createEmptyReturnDraft('2026-27','ITR-4','old');draft.personal.name='Asha';draft.deductions.section80D.selfFamily.preventiveCheckup=1000;const result=await new HttpReturnRepository().save(7,draft);expect(axiosInstance.put).toHaveBeenCalledOnce();expect(result).toMatchObject({assessmentYear:'2026-27',form:'ITR-4',regime:'old',personal:{name:'Asha'}});expect(result.deductions.section80D.selfFamily.preventiveCheckup).toBe(1000);expect(result.compatibility?.unknownFields).not.toMatchObject({message:'saved'});result.personal.name='Changed';expect(draft.personal.name).toBe('Asha');});
});
